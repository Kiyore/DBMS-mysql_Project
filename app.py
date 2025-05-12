from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL connection configuration
db_config = {
    'host': '202311050-dbms.mysql.database.azure.com',
    'user': 'jenil50',
    'password': 'Azuredb99.',
    'database': 'PROJECT2'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required', 'danger')
            return redirect(url_for('login'))

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True, buffered=True)

            cursor.execute('SELECT password FROM credentials WHERE id = %s', (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = username
                
                # Determine user type and fetch name
                if username.startswith('D'):  # Donor
                    donor_id = username[1:]
                    cursor.execute('SELECT donor_name FROM donor WHERE donor_id = %s', (donor_id,))
                    user_data = cursor.fetchone()
                    if not user_data:
                        flash('User data not found', 'danger')
                        return redirect(url_for('login'))
                    session['user_type'] = 'Donor'
                    session['name'] = user_data['donor_name']
                elif username.startswith('d'):  # Distributor
                    distributor_id = username[1:]
                    cursor.execute('SELECT distributor_name FROM distributor WHERE distributor_id = %s', (distributor_id,))
                    user_data = cursor.fetchone()
                    if not user_data:
                        flash('User data not found', 'danger')
                        return redirect(url_for('login'))
                    session['user_type'] = 'Distributor'
                    session['name'] = user_data['distributor_name']
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html',
                         name=session.get('name'),
                         user_type=session.get('user_type'),
                         user_id=session.get('user_id'))

# Modified view_table route to allow donors to view all tables
@app.route('/view_table/<table_name>')
def view_table(table_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    allowed_tables = ['donor', 'distributor', 'availability', 'donations']
    if table_name not in allowed_tables:
        flash('Invalid table requested', 'danger')
        return redirect(url_for('dashboard'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if table_name == 'availability':
            # Modified query to join with donor table
            query = '''
                SELECT a.*, d.donor_name, d.donor_address 
                FROM availability a
                JOIN donor d ON a.donor_id = d.donor_id
            '''
            
            # For donors, only show their own availability
            if session['user_type'] == 'Donor':
                donor_id = session['user_id'][1:]
                query += ' WHERE a.donor_id = %s'
                cursor.execute(query, (donor_id,))
            else:
                cursor.execute(query)
        else:
            cursor.execute(f"SELECT * FROM {table_name}")

        data = cursor.fetchall()
        return render_template('table_view.html',
                            table_name=table_name,
                            data=data)
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Add these new routes

@app.route('/edit_availability/<int:availability_id>', methods=['GET', 'POST'])
def edit_availability(availability_id):
    if 'user_id' not in session or not session['user_id'].startswith('D'):
        return redirect(url_for('login'))

    donor_id = session['user_id'][1:]  # Extract numeric ID from D123 format

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify the record belongs to this donor
        cursor.execute('''
            SELECT * FROM availability 
            WHERE availability_id = %s AND donor_id = %s
        ''', (availability_id, donor_id))
        record = cursor.fetchone()

        if not record:
            flash('Record not found or access denied', 'danger')
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            amount = request.form.get('amount')
            meal_type = request.form.get('meal_type')
            notes = request.form.get('notes', '')

            if not amount or not meal_type:
                flash('Amount and meal type are required', 'danger')
                return redirect(url_for('edit_availability', availability_id=availability_id))

            # Update the record
            cursor.execute('''
                UPDATE availability 
                SET amount = %s, meal_type = %s, notes = %s
                WHERE availability_id = %s AND donor_id = %s
            ''', (amount, meal_type, notes, availability_id, donor_id))
            
            conn.commit()
            flash('Availability updated successfully!', 'success')
            return redirect(url_for('view_table', table_name='availability'))

        return render_template('edit_availability.html', record=record)

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Database error: {err}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/delete_availability/<int:availability_id>')
def delete_availability(availability_id):
    if 'user_id' not in session or not session['user_id'].startswith('D'):
        return redirect(url_for('login'))

    donor_id = session['user_id'][1:]  # Extract numeric ID from D123 format

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify the record belongs to this donor before deleting
        cursor.execute('''
            DELETE FROM availability 
            WHERE availability_id = %s AND donor_id = %s
        ''', (availability_id, donor_id))
        
        conn.commit()
        flash('Availability record deleted successfully!', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Database error: {err}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('view_table', table_name='availability'))

@app.route('/add_availability', methods=['GET', 'POST'])
def add_availability():
    if 'user_id' not in session or session['user_type'] != 'Donor':
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form.get('amount')
        meal_type = request.form.get('meal_type')
        notes = request.form.get('notes', '')

        if not amount or not meal_type:
            flash('Amount and meal type are required', 'danger')
            return redirect(url_for('add_availability'))

        donor_id = session['user_id'][1:]  # Extract numeric ID from D123 format

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO availability (donor_id, amount, meal_type, notes)
                VALUES (%s, %s, %s, %s)
            ''', (donor_id, amount, meal_type, notes))
            
            conn.commit()
            flash('Availability added successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Database error: {err}', 'danger')
            return redirect(url_for('add_availability'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('add_availability.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        required_fields = ['name', 'password', 'user_type', 'phone', 'email']
        missing_fields = [field for field in required_fields if field not in request.form]
        
        if missing_fields:
            flash(f'Missing fields: {", ".join(missing_fields)}', 'danger')
            return redirect(url_for('register'))

        form_data = {
            'name': request.form['name'],
            'password': request.form['password'],
            'user_type': request.form['user_type'],
            'phone': request.form['phone'],
            'email': request.form['email'],
            'address': request.form.get('address', '')
        }

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(buffered=True)

            if form_data['user_type'] == 'donor':
                cursor.execute('''
                    INSERT INTO donor (donor_name, donor_phone, donor_email, donor_address)
                    VALUES (%s, %s, %s, %s)
                ''', (form_data['name'], form_data['phone'], form_data['email'], form_data['address']))
                
                donor_id = cursor.lastrowid
                user_id = f"D{donor_id}"
            
            elif form_data['user_type'] == 'receiver':
                cursor.execute('''
                    INSERT INTO distributor (distributor_name, distributor_phone, distributor_email, distributor_address)
                    VALUES (%s, %s, %s, %s)
                ''', (form_data['name'], form_data['phone'], form_data['email'], form_data['address']))
                
                distributor_id = cursor.lastrowid
                user_id = f"d{distributor_id}"
            
            else:
                flash('Invalid user type', 'danger')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(form_data['password'])
            cursor.execute('''
                INSERT INTO credentials (id, password)
                VALUES (%s, %s)
            ''', (user_id, hashed_password))
            
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        
        except mysql.connector.Error as err:
            if conn:
                conn.rollback()
            flash(f'Database error: {err}', 'danger')
            return redirect(url_for('register'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('register.html')

@app.route('/add_donation', methods=['GET', 'POST'])
def add_donation():
    if 'user_id' not in session or session['user_type'] != 'Distributor':
        return redirect(url_for('login'))

    if request.method == 'POST':
        donor_id = request.form.get('donor_id')
        distributor_id = session['user_id'][1:]  # Extract numeric ID from d123 format
        note = request.form.get('note', '')
        people_served = request.form.get('people_served')
        area_served = request.form.get('area_served')
        date_serve = request.form.get('date_serve')
        meal_type = request.form.get('meal_type')

        if not all([donor_id, people_served, area_served, date_serve, meal_type]):
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_donation'))

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert the donation
            cursor.execute('''
                INSERT INTO donations 
                (donor_id, distributor_id, note, people_served, area_served, date_serve, meal_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (donor_id, distributor_id, note, people_served, area_served, date_serve, meal_type))
            
            conn.commit()
            flash('Donation recorded successfully!', 'success')
            return redirect(url_for('view_table', table_name='donations'))
        
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Database error: {err}', 'danger')
            return redirect(url_for('add_donation'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # For GET request, show the form with donor list
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all donors
        cursor.execute('SELECT donor_id, donor_name FROM donor')
        donors = cursor.fetchall()
        
        return render_template('add_donation.html', donors=donors)
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)