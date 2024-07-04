import logging
import time
import uuid
import json
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import paypalrestsdk
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Configuration for logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Flask app and configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'hiya'  # Replace 'your_secret_key' with a random string
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banking.db'  # Database URI for SQLite
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# PayPal configuration
paypalrestsdk.configure({
    'mode': 'sandbox',  # Use 'sandbox' for testing, 'live' for production
    'client_id': 'AUK1X_-2S_gm1mwohAwLEY8cDa-JNJzn2d5dkq_dt6De_Q3UJSbhIA_PNMB8OX6TLef7FD3OJX28yNOc',  # Replace with your PayPal client ID
    'client_secret': 'EFekxbGHs2Q0DRuiTcOf6iKExsXeihhaTXW64X39EGXF2hM2oL-etsdql10-HHtrSNjLTWknOTlqTs8B'  # Replace with your PayPal client secret
})

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    paypal_email = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
# Home route
@app.route('/')
def home():
    return render_template('index.html', user=current_user)

# Games route
@app.route('/games')
def games():
    return render_template('games.html', user=current_user)

# Game cards route
@app.route('/gamesCards')
@login_required
def game_cards():
    user = User.query.get(session['user_id'])
    return render_template('gamesCards.html', user=user)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        paypal_email = request.form['paypal_email']
        hashed_password = generate_password_hash(password)  # Default method is 'pbkdf2:sha256'
        
        # Check if user already exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different username.', 'error')
            return redirect(url_for('error'))

        new_user = User(username=username, password_hash=hashed_password, paypal_email=paypal_email)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', user=current_user)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.debug(f'Trying to log in user: {username}')
        user = User.query.filter_by(username=username).first()
        if user:
            logger.debug('User found in database')
            if check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                login_user(user)
                logger.debug('Login successful')
                flash('Login successful.', 'success')
                return redirect(url_for('dashboard'))
            else:
                logger.debug('Password check failed')
        else:
            logger.debug('User not found in database')
        flash('Login failed. Check your username and password.', 'error')
        return redirect(url_for('error'))
    return render_template('login.html', user=current_user)

# Error route
@app.route('/error')
def error():
    return render_template('error.html')

# Error Transaction route
@app.route('/error_transaction')
def error_transaction():
    return render_template('error_transaction.html')

# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    success_message = request.args.get('success_message')
    return render_template('dashboard.html', user=user, success_message=success_message)


# Add Money route
@app.route('/add_money', methods=['GET', 'POST'])
@login_required
def add_money():
    if request.method == 'POST':
        amount = request.form['amount']
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"},
            "redirect_urls": {
                "return_url": url_for('payment_execute', _external=True),
                "cancel_url": url_for('error_transaction', _external=True)},
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": "Add Money",
                        "sku": "001",
                        "price": amount,
                        "currency": "GBP",
                        "quantity": 1}]},
                "amount": {
                    "total": amount,
                    "currency": "GBP"},
                "description": "Add money to your account"}]})

        if payment.create():
            for link in payment.links:
                if link.rel == "approval_url":
                    approval_url = str(link.href)
                    return redirect(approval_url)
            flash('Something went wrong.', 'error')
            return redirect(url_for('error_transaction'))
        else:
            flash('Payment creation failed.', 'error')
            return redirect(url_for('error_transaction'))
    return render_template('add_money.html', user=current_user)

# Payment execute route
@app.route('/payment_execute')
@login_required
def payment_execute():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        user = User.query.get(session['user_id'])
        amount = float(payment.transactions[0].amount.total)
        user.balance += amount
        db.session.commit()
        time.sleep(2)  # Add a 2-second delay
        return render_template('success.html', user=current_user)
    else:
        flash('Payment execution failed.', 'error')
        return redirect(url_for('error_transaction'))

# Withdraw Money route
@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    idd = str(uuid.uuid4())
    if request.method == 'POST':
        amount = float(request.form['amount'])
        user = User.query.get(session['user_id'])
        if user.balance >= amount:
            payout = paypalrestsdk.Payout({
                "sender_batch_header": {
                    "sender_batch_id": idd,
                    "email_subject": "You have a payout!"
                },
                "items": [{
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": amount,
                        "currency": "GBP"
                    },
                    "receiver": user.paypal_email,
                    "note": "Thank you for using our service!",
                    "sender_item_id": "item_" + str(user.id)
                }]
            })

            if payout.create():
                logger.info('Payout created successfully')
                user.balance -= amount
                db.session.commit()
                time.sleep(2)  # Add a 2-second delay
                return render_template('success.html', user=current_user)
            else:
                logger.error('Payout creation failed: %s', payout.error)
                flash('Payout creation failed.', 'error')
                return redirect(url_for('error_transaction'))
        else:
            logger.warning('Insufficient balance for user %s', user.username)
            flash('Insufficient balance.', 'error')
            return redirect(url_for('error_transaction'))
    return render_template('withdraw.html', user=current_user)

# Update Balance route
@app.route('/update_balance', methods=['POST'])
@login_required
def update_balance():
    data = request.get_json()
    new_balance = data.get('new_balance')
    user = User.query.get(session['user_id'])
    if new_balance is not None:
        user.balance = new_balance
        db.session.commit()
        return jsonify({'success': True}), 200
    return jsonify({'success': False}), 400

# Logout route
@app.route('/logout')
def logout():
    logout_user()
    session.pop('user_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))


#GAMES ROUTES::::
# Plinko route
@app.route('/plinko')
@login_required
def plinko():
    user = User.query.get(session['user_id'])
    return render_template('plinko.html', user=user)

# Blackjack route
@app.route('/cardgame')
@login_required
def blackjack():
    user = User.query.get(session['user_id'])
    return render_template('cardgame.html', user=user)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
