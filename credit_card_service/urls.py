from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from user.views import RegisterUserView, ApplyLoanView
from repayment.views import MakePaymentView, StatementView

def home_view(request):
    return HttpResponse("""
        <html>
            <head>
                <title>Credit Card Service</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 0;
                        background-color: #f4f4f9;
                        color: #333;
                    }
                    header {
                        background-color: #4CAF50;
                        color: white;
                        padding: 10px 20px;
                        text-align: center;
                    }
                    h1 {
                        margin: 0;
                    }
                    p {
                        text-align: center;
                        font-size: 18px;
                    }
                    ul {
                        list-style-type: none;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                    }
                    li {
                        margin: 0 15px;
                    }
                    a {
                        text-decoration: none;
                        color: #4CAF50;
                        font-weight: bold;
                        transition: color 0.3s;
                    }
                    a:hover {
                        color: #087f23;
                    }
                    footer {
                        text-align: center;
                        margin-top: 20px;
                        font-size: 14px;
                        color: #666;
                    }
                </style>
            </head>
            <body>
                <header>
                    <h1>Welcome to the Credit Card Service</h1>
                </header>
                <p>Explore our services:</p>
                <ul>
                    <li><a href="/admin/">Admin Panel</a></li>
                    <li><a href="/api/register-user/">Register User</a></li>
                    <li><a href="/api/apply-loan/">Apply for a Loan</a></li>
                    <li><a href="/api/make-payment/">Make a Payment</a></li>
                    <li><a href="/api/get-statement/">Get Statement</a></li>
                </ul>
            </body>
        </html>
    """)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/register-user/', RegisterUserView.as_view(), name='register-user'),
    path('api/apply-loan/', ApplyLoanView.as_view(), name='apply-loan'),
    path('api/make-payment/', MakePaymentView.as_view(), name='make-payment'),
    path('api/get-statement/', StatementView.as_view(), name='get-statement'),
    path('', home_view, name='home'),
]
