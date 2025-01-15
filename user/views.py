from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user.models import User, Loan
from user.tasks import calculate_credit_score
import json
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import render
from datetime import datetime


class RegisterUserView(APIView):
    """
    Handles user registration.

    POST:
    - Registers a new user with required fields (name, aadhar_id, email_id, annual_income).
    - Initiates a Celery task to calculate the user's credit score based on transaction data.

    GET:
    - Returns a styled HTML table displaying all registered users, including Aadhar Number.
    """

    def validate_data(self, data):
        """
        Validates the input data and ensures all required fields are present.
        """
        try:
            return data['name'], data['aadhar_id'], data['email_id'], data['annual_income']
        except KeyError as e:
            raise KeyError(f"Missing field: {str(e)}")

    def get(self, request):
        """Render an HTML form and display all registered users."""
        users = User.objects.all()
        user_data = [
            {
                "id": user.user_id,
                "name": user.name,
                "email": user.email,
                "aadhar": user.aadhar_number,
                "income": user.annual_income,
            }
            for user in users
        ]

        # HTML content with inline CSS
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Registered Users</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; }
                h1, h2 { text-align: center; color: #4CAF50; }
                form { max-width: 500px; margin: 20px auto; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 8px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input { width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
                button { display: block; width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-size: 16px; }
                button:hover { background-color: #45a049; }
                table { margin: 20px auto; border-collapse: collapse; width: 90%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                tr:hover { background-color: #ddd; }
            </style>
        </head>
        <body>
            <h1>Register User</h1>
            <form method="POST" action="/api/register-user/">
                <label for="name">Name</label>
                <input type="text" id="name" name="name" placeholder="Enter your name" required>
                
                <label for="aadhar_id">Aadhar ID</label>
                <input type="text" id="aadhar_id" name="aadhar_id" placeholder="Enter your Aadhar ID" required>
                
                <label for="email_id">Email</label>
                <input type="email" id="email_id" name="email_id" placeholder="Enter your email" required>
                
                <label for="annual_income">Annual Income</label>
                <input type="number" id="annual_income" name="annual_income" placeholder="Enter your annual income" required>
                
                <button type="submit">Register</button>
            </form>
            <h2>Registered Users</h2>
            <table>
                <thead>
                    <tr>
                        <th>User ID</th>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Aadhar Number</th>
                        <th>Annual Income</th>
                    </tr>
                </thead>
                <tbody>
        """

        for user in user_data:
            html_content += f"""
                <tr>
                    <td>{user['id']}</td>
                    <td>{user['name']}</td>
                    <td>{user['email']}</td>
                    <td>{user['aadhar']}</td>
                    <td>{user['income']}</td>
                </tr>
            """

        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type="text/html")

    def post(self, request):
        try:
            # Parse and validate request data
            if not request.body:
                raise ValueError("Request body is empty.")

            data = json.loads(request.body)
            name, aadhar_number, email, annual_income = self.validate_data(data)

            # Create a new user
            user = User(
                name=name,
                aadhar_number=aadhar_number,
                email=email,
                annual_income=annual_income,
            )
            user.save()

            # Trigger Celery task to calculate credit score
            calculate_credit_score.delay(user.user_id)

            return Response(
                data={
                    "user_id": str(user.user_id),
                    "message": "User registered successfully. Credit score calculation initiated.",
                },
                status=status.HTTP_201_CREATED,
            )

        except json.JSONDecodeError:
            return Response(
                data={"error": "Invalid JSON format. Please provide valid JSON data."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            return Response(
                data={"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except KeyError as e:
            return Response(
                data={"error": f"Missing field: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                data={"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ApplyLoanView(APIView):
    """
    Handles Credit Card Loan applications.

    GET:
    - Displays an HTML form to apply for a loan.
    - Lists all existing credit card loans.

    POST:
    - Processes loan applications submitted via JSON or the HTML form.
    """

    def get(self, request):
        """Render an HTML form for loan application and list all loans."""
        loans = Loan.objects.filter(loan_type="Credit Card")
        loan_data = [
            {
                "loan_id": loan.loan_id,
                "user_name": loan.user.name,
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "term_period": loan.term_period,
                "disbursement_date": loan.disbursement_date.strftime('%d-%m-%Y'),
            }
            for loan in loans
        ]

        # HTML Content with Inline CSS and Form
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Apply for a Credit Card Loan</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333; }
                h1, h2 { text-align: center; color: #4CAF50; }
                form { max-width: 500px; margin: 20px auto; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 8px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, select { width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
                button { display: block; width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-size: 16px; }
                button:hover { background-color: #45a049; }
                table { margin: 20px auto; border-collapse: collapse; width: 90%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                tr:hover { background-color: #ddd; }
                .no-data { text-align: center; font-size: 18px; color: #666; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Apply for a Credit Card Loan</h1>
            <form method="POST" action="/api/apply-loan/">
                <label for="user_id">User ID</label>
                <input type="text" id="user_id" name="user_id" placeholder="Enter your User ID" required>
                
                <label for="loan_amount">Loan Amount</label>
                <input type="number" id="loan_amount" name="loan_amount" placeholder="Enter loan amount (max ₹5000)" required>
                
                <label for="disbursement_date">Disbursement Date</label>
                <input type="date" id="disbursement_date" name="disbursement_date" required>
                
                <button type="submit">Submit Application</button>
            </form>
            
            <h2>Existing Loans</h2>
        """

        if loan_data:
            html_content += """
            <table>
                <thead>
                    <tr>
                        <th>Loan ID</th>
                        <th>User Name</th>
                        <th>Loan Amount</th>
                        <th>Interest Rate (%)</th>
                        <th>Term Period (Months)</th>
                        <th>Disbursement Date</th>
                    </tr>
                </thead>
                <tbody>
            """
            for loan in loan_data:
                html_content += f"""
                    <tr>
                        <td>{loan['loan_id']}</td>
                        <td>{loan['user_name']}</td>
                        <td>{loan['loan_amount']}</td>
                        <td>{loan['interest_rate']}</td>
                        <td>{loan['term_period']}</td>
                        <td>{loan['disbursement_date']}</td>
                    </tr>
                """
            html_content += """
                </tbody>
            </table>
            """
        else:
            html_content += """
            <div class="no-data">No credit card loans available.</div>
            """

        html_content += """
        </body>
        </html>
        """
        return HttpResponse(html_content, content_type="text/html")

    def post(self, request):
        """Process loan applications submitted via JSON or HTML form."""
        # Handle HTML form submission
        if request.content_type == "application/x-www-form-urlencoded":
            user_id = request.POST.get("user_id")
            loan_amount = int(request.POST.get("loan_amount"))
            disbursement_date = request.POST.get("disbursement_date")
        else:  # Handle JSON submission
            data = json.loads(request.body)
            user_id = data.get("user_id")
            loan_amount = int(data.get("loan_amount"))
            disbursement_date = data.get("disbursement_date")

        # Fetch user from the database
        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return HttpResponse("<h1>User not found. Please register before applying for a loan.</h1>", status=404)

        # Eligibility Checks
        if user.credit_score < 450:
            return HttpResponse("<h1>Loan declined. Credit score is too low.</h1>", status=400)
        if user.annual_income < 150000:
            return HttpResponse("<h1>Loan declined. Annual income is too low.</h1>", status=400)
        if loan_amount > 5000:
            return HttpResponse("<h1>Loan declined. Loan amount exceeds ₹5000.</h1>", status=400)

        # Parse and validate the disbursement date
        try:
            disbursement_date = datetime.strptime(disbursement_date, '%Y-%m-%d')
        except ValueError:
            return HttpResponse("<h1>Invalid date format. Use YYYY-MM-DD.</h1>", status=400)

        # Create loan record
        loan = Loan(
            user=user,
            loan_amount=loan_amount,
            loan_type="Credit Card",
            interest_rate=12,
            term_period=12,
            disbursement_date=disbursement_date,
            principal_balance=loan_amount
        )
        loan.save()

        return HttpResponse("<h1>Loan application successful!</h1>", status=200)