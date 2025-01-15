from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from user.models import User, Loan
from repayment.models import Payment, Transaction
from repayment.tasks import update_next_emis
from datetime import timedelta
from django.core.exceptions import ObjectDoesNotExist


class MakePaymentView(APIView):
    """
    Handles loan payments.
    
    GET:
    - Renders a form for users to input payment details.
    
    POST:
    - Processes the payment based on the input details.
    """

    def handle_exception(self, exc):
        if isinstance(exc, KeyError):
            return Response(
                data={"error": f"Invalid data: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, ObjectDoesNotExist):
            return Response(
                data={"error": f"Not Found: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, ValueError):
            return Response(
                data={"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(exc)

    def get(self, request):
        """Render an HTML form for making payments."""
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Make Payment</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; }
                h1 { text-align: center; color: #4CAF50; margin-top: 20px; }
                form { max-width: 500px; margin: 20px auto; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 8px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input { width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
                button { display: block; width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-size: 16px; }
                button:hover { background-color: #45a049; }
                .error { color: red; text-align: center; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>Make a Payment</h1>
            <form method="POST" action="/api/make-payment/">
                <label for="loan_id">Loan ID</label>
                <input type="text" id="loan_id" name="loan_id" placeholder="Enter your Loan ID" required>
                
                <label for="amount">Payment Amount</label>
                <input type="number" id="amount" name="amount" placeholder="Enter payment amount" required>
                
                <button type="submit">Submit Payment</button>
            </form>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type="text/html")

    def post(self, request):
        try:
            # Parse input data
            if request.content_type == "application/x-www-form-urlencoded":
                loan_id = request.POST.get("loan_id")
                amount = int(request.POST.get("amount"))
            else:
                data = json.loads(request.body)
                loan_id = data["loan_id"]
                amount = round(data["amount"])

            # Fetch the loan
            loan = Loan.objects.get(loan_id=loan_id)

            if loan.loan_status in ["STOPPED", "REPAID"]:
                raise ValueError("Loan cannot be processed. Status: " + loan.loan_status)

            # Calculate due and process payment
            total_due, duration_days = self.get_total_due_and_days(loan_id, loan.disbursement_date)
            min_due = round(self.get_min_due(loan, duration_days))

            if amount < min_due:
                raise ValueError(f"Minimum due payment is {min_due}.")

            self.pay_amount(amount, loan_id, min_due)

            # Trigger EMI updates if necessary
            if amount > total_due:
                update_next_emis.delay(loan_id)

            return Response(data={"message": "Payment processed successfully."}, status=status.HTTP_200_OK)

        except Exception as exc:
            return self.handle_exception(exc)

    def get_total_due_and_days(self, loan_id, loan_disbursement_date):
        """Calculate total due and days duration."""
        all_payments = Payment.objects.filter(loan=loan_id)
        total_due = 0
        i = 0

        for payment in all_payments:
            if payment.status in ["NOT_DUE", "COMPLETED"]:
                continue
            if payment.status == "PARTIALLY_COMPLETED":
                total_due += payment.emi_amount - payment.total_paid
            elif payment.status == "DUE":
                total_due += payment.emi_amount
            i += 1

        if i == 0:
            raise ValueError("No payments are due.")
        
        duration = (all_payments[i - 1].due_date - loan_disbursement_date).days if i == 1 else (
            all_payments[i - 1].due_date - all_payments[i - 2].due_date).days
        
        return total_due, duration

    def get_min_due(self, loan, days):
        """Calculate the minimum due amount."""
        return round((loan.principal_balance * 0.03) + (loan.principal_balance * days * loan.interest_rate / 365 / 100), 2)

    def pay_amount(self, amount, loan_id, min_due):
        """Handle the payment logic."""
        loan = Loan.objects.get(loan_id=loan_id)
        transaction = Transaction(loan=loan, amount=amount)
        transaction.save()

        # Process payments
        if loan.principal_balance == amount:
            loan.principal_balance = 0
            loan.status = "REPAID"
        else:
            loan.principal_balance -= amount
        loan.save()


class StatementView(APIView):
    """
    Handles loan account statements.

    GET:
    - Renders an HTML form to input a loan ID.
    - Displays the statement of payments for the provided loan ID.
    """

    def get(self, request):
        loan_id = request.GET.get("loan_id")

        if not loan_id:
            # Render the form
            html_content = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Loan Account Statement</title>
                <style>
                    body { font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }
                    h1 { text-align: center; color: #4CAF50; margin-bottom: 20px; }
                    form { max-width: 400px; margin: 20px auto; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 8px; }
                    label { display: block; margin-bottom: 10px; font-weight: bold; }
                    input { width: 100%; padding: 8px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; }
                    button { width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-size: 16px; }
                    button:hover { background-color: #45a049; }
                </style>
            </head>
            <body>
                <h1>Loan Account Statement</h1>
                <form method="get" action="">
                    <label for="loan_id">Enter Loan ID</label>
                    <input type="text" id="loan_id" name="loan_id" placeholder="Loan ID" required>
                    <button type="submit">View Statement</button>
                </form>
            </body>
            </html>
            """
            return HttpResponse(html_content, content_type="text/html")

        # If a loan ID is provided, fetch the payment statement
        payments = Payment.objects.filter(loan=loan_id)

        if not payments.exists():
            # If no payments are found, show a message
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Loan Account Statement</title>
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; text-align: center; }}
                    h1 {{ color: #4CAF50; }}
                </style>
            </head>
            <body>
                <h1>Loan Account Statement</h1>
                <p>No payments found for Loan ID: {loan_id}</p>
            </body>
            </html>
            """
            return HttpResponse(html_content, content_type="text/html")

        # If payments are found, display them in a table
        account_statement = PaymentSerializer(payments, many=True).data
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Loan Account Statement</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; padding: 20px; }
                h1 { text-align: center; color: #4CAF50; margin-bottom: 20px; }
                table { width: 90%; margin: 0 auto; border-collapse: collapse; }
                th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                tr:hover { background-color: #ddd; }
            </style>
        </head>
        <body>
            <h1>Loan Account Statement</h1>
            <table>
                <thead>
                    <tr>
                        <th>Payment ID</th>
                        <th>Loan ID</th>
                        <th>EMI Amount</th>
                        <th>Total Paid</th>
                        <th>Status</th>
                        <th>Due Date</th>
                    </tr>
                </thead>
                <tbody>
        """

        for payment in account_statement:
            html_content += f"""
            <tr>
                <td>{payment['payment_id']}</td>
                <td>{payment['loan']}</td>
                <td>{payment['emi_amount']}</td>
                <td>{payment['total_paid']}</td>
                <td>{payment['status']}</td>
                <td>{payment['due_date']}</td>
            </tr>
            """

        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type="text/html")
