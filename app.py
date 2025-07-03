from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import pyodbc
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from same directory as app.py
base_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=base_dir / '.env')

conn_str = os.getenv("CONN_STR")
import os
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

print("Templates:", os.listdir(template_dir))
print("Current directory:", os.getcwd())
app.secret_key = '4be5b4b95f0c076bc1bb51bfdc45e48794046c281d2f95060c4b2d9cf3d757b9'

VALID_SIGNUP_CODE = "SECRET123"

import hashlib

def check_login(username, password):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Query user from DB
    cursor.execute("SELECT password_hash FROM Users WHERE user_name = ?", (username,))
    result = cursor.fetchone()

    if result:
        stored_hash = result[0]
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        return input_hash == stored_hash
    else:
        return render_template('login.html', error="Login failed - user not found.")
    
def log_event(username, action_type, details=None):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM Users WHERE user_name = ?", (username,))
    result = cursor.fetchone()
    user_id = result[0] if result else None

    cursor.execute("""
        INSERT INTO app_audit_log (user_id, action_type, target_table, target_id, details, timestamp)
        VALUES (?, ?, ?, ?, ?, GETDATE())
    """, (
        user_id,
        action_type,
        'Users',
        user_id,
        details
    ))

    conn.commit()
    conn.close()

@app.route('/')
def root_redirect():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if check_login(username, password):
            # ✅ Pull user_id and family_id from the DB
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, family_id, Role_id FROM Users WHERE user_name = ? and is_active = 1", (username,))
            result = cursor.fetchone()
            conn.close()

            if result:
                session['logged_in'] = True
                session['username'] = username
                session['user_id'] = result[0]
                session['family_id'] = result[1]
                session['role_id'] = result[2]

                log_event(username, 'Login Success')
                return redirect(url_for('dashboard'))
            else:
                # fallback if somehow user found in check_login but not here
                return render_template('login.html', error="Login failed - user not found.")

        else:
            log_event(username, 'Login Failed', details="Invalid credentials")
            return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form['reset_username']
        new_password = request.form['new_password']
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest()

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Check if the user exists first
        cursor.execute("SELECT 1 FROM Users WHERE user_name = ?", (username,))
        if cursor.fetchone() is None:
            conn.close()
            return render_template('reset_password.html', error="Username not found. Please try again.")

        # Proceed with update if user exists
        cursor.execute("""
            UPDATE Users
            SET password_hash = ?
            WHERE user_name = ?
        """, (hashed_password, username))
        conn.commit()
        conn.close()

        log_event(username, 'Password Reset', details="Password changed via reset page")
        return render_template('reset_password.html', message="Password reset successful. You may now log in.")

    return render_template('reset_password.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    print("ROUTE HIT")

    if request.method == 'POST':
        print("POST received")

        # Get form data
        family_name = request.form['family_name']
        admin_name = request.form['admin_name']
        admin_password = request.form['admin_password']
        email = request.form['email']
        submitted_code = request.form['security_code']

        # Validate security code
        if submitted_code != VALID_SIGNUP_CODE:
            print("Invalid security code")
            return render_template('signup.html', error="Invalid security code.")

        # Hash the password
        hashed_password = hashlib.sha256(admin_password.encode()).hexdigest()
        print("Password hashed")

        try:
            conn = pyodbc.connect(conn_str)
            conn.autocommit = False
            cursor = conn.cursor()
            print("DB connected")

            # Insert family with placeholder who = 2002
            cursor.execute("""
                INSERT INTO Families (family_name, date_created, is_active, created_by)
                OUTPUT INSERTED.family_id
                VALUES (?, GETDATE(), 1, ?)
            """, (family_name, 2002))

            row = cursor.fetchone()
            if row is None or row[0] is None:
                conn.rollback()
                print("Family insert failed")
                return render_template('signup.html', error="Failed to create family.")
            family_id = int(row[0])
            print(f"Family insert returned: {family_id}")

            # Insert admin user and get User_ID directly
            cursor.execute("""
                INSERT INTO Users (User_name, password_hash, Role_id, Family_id, email, date_created, is_active)
                OUTPUT INSERTED.User_ID
                VALUES (?, ?, 1, ?, ?, GETDATE(), 1)
            """, (admin_name, hashed_password, family_id, email))

            row = cursor.fetchone()
            if row is None or row[0] is None:
                conn.rollback()
                print("User insert failed")
                return render_template('signup.html', error="Failed to create user.")
            user_id = int(row[0])
            print(f"User insert returned: {user_id}")

            # Update Families table with actual admin ID
            cursor.execute("""
                UPDATE Families
                SET created_by = ?
                WHERE family_id = ?
            """, (user_id, family_id))

            if cursor.rowcount != 1:
                conn.rollback()
                print("Update failed")
                return render_template('signup.html', error="Failed to assign admin user to family.")
            print("Family updated with admin user")

            conn.commit()
            print("Transaction committed")
            flash("Signup successful! Please log in.")
            return redirect(url_for('login'))

        except pyodbc.IntegrityError as e:
            conn.rollback()
            print("INTEGRITY ERROR:", str(e))
            msg = str(e).lower()
            if "families" in msg and "unique" in msg:
                return render_template('signup.html', error="Family name already exists.")
            elif "users" in msg and "unique" in msg:
                return render_template('signup.html', error="Username or email already taken.")
            else:
                return render_template('signup.html', error=f"Database integrity error: {str(e)}")

        except Exception as e:
            conn.rollback()
            print("GENERAL ERROR:", str(e))
            return render_template('signup.html', error=f"Unexpected error: {str(e)}")

        finally:
            conn.close()
            print("Connection closed")

    print("GET request - rendering form")
    return render_template('signup.html')

@app.context_processor
def inject_my_active_chores():
    if not session.get('logged_in'):
        return dict(my_active_chores=0, Need_approval=0)

    user_id = session.get('user_id')
    family_id = session.get('family_id')

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(assignment_id) FROM chore_assignments 
        WHERE assigned_to = ? AND completion_status in ('Pending', 'Sent Back')
    """, (user_id,))
    result = cursor.fetchone()
    my_active_chores = result[0] if result else 0

    cursor.execute("""
        SELECT COUNT(a.assignment_id) FROM chore_assignments as a
        inner join users as u on u.user_id = a.assigned_to
        WHERE u.family_id = ? AND a.completion_status = 'Submitted'
    """, (family_id,))
    result = cursor.fetchone()
    Need_approval = result[0] if result else 0
    
    conn.close()

    return dict(active_chores=my_active_chores, chore_completions=Need_approval)

@app.context_processor
def inject_role():
    return dict(role_id=session.get('role_id'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    user_id = session.get('user_id')
    family_id = session.get('family_id')

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # --- top left ---
    cursor.execute("""
    Exec sp_topleftdashboard ?,?
""", (user_id, family_id,))
    Top_left = cursor.fetchall()

        # --- top right ---
    cursor.execute("""
    Exec sp_hallofFame ?
""", (family_id,))
    Top_right1 = cursor.fetchall()
    cursor.nextset()
    Top_right2 = cursor.fetchall()
    cursor.nextset()    
    Top_right3 = cursor.fetchall()
    cursor.nextset()
    Top_right4 = cursor.fetchall()

        # --- Chores split ---
    range = request.args.get('range', 'My_Chores')

    if range == 'My_Chores':
        cursor.execute("""
        Select
u.user_name,
cl.chore_name,
Count(*) as total
From chore_assignments as ca
inner join users as u 
on ca.completed_by = u.User_ID
inner join chores_list as cl
on ca.Chore_ID = cl.Chore_id
Where ca.Completion_Status = 'complete' and u.family_id = ? and user_id = ?
Group by 
u.user_name,
cl.chore_name                   
    """, (family_id, user_id))

    else: 
         cursor.execute("""
Select
cl.chore_name,
Count(*) as total
From chore_assignments as ca
inner join users as u 
on ca.completed_by = u.User_ID
inner join chores_list as cl
on ca.Chore_ID = cl.Chore_id
Where ca.Completion_Status = 'complete' and u.family_id = ?
Group by 
cl.chore_name            
    """, (family_id))

    Chores_split = cursor.fetchall() 
    labels = [row.chore_name for row in Chores_split]
    values = [row.total for row in Chores_split]

            # --- bottom right ---
    cursor.execute("""
    Exec sp_last30days ?
""", (family_id,))
    bottom_left = cursor.fetchall()
    headers = [column[0] for column in cursor.description]    
    stacked_labels = headers[1:]  # Dates

    color_palette = [
        '#FF6384', '#36A2EB', '#FFCE56',
        '#4BC0C0', '#9966FF', '#FF9F40',
        '#76D7C4', '#F7DC6F', '#C39BD3', '#A3E4D7'
    ]

    stacked_datasets = []

    for idx, row in enumerate(bottom_left):
        username = row[0]
        values = row[1:]

        dataset = {
            'label': username,
            'data': values,
            'backgroundColor': color_palette[idx % len(color_palette)]
        }
        stacked_datasets.append(dataset)                  
                 
    conn.close()
     
    return render_template(
        "dashboard.html",
        Top_left=Top_left,
        Top_right1=Top_right1,
        Top_right2=Top_right2,
        Top_right3=Top_right3,
        Top_right4=Top_right4,
        Chores_split=Chores_split,
        selected_range=range,
        pie_labels=labels,
        pie_values=values,
        bottom_left=bottom_left,
        headers=headers,
        stacked_labels=stacked_labels,
        stacked_datasets=stacked_datasets
        
    )


@app.route('/leaderboard')
def leaderboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    family_id = session.get('family_id') 

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # --- All-time leaderboard ---
    cursor.execute("""
    SELECT Name, Total_Points FROM vw_FamilyLeaderboard
    WHERE family_id = ?
    Order by Total_points desc
""", (family_id,))
    all_time_data = cursor.fetchall()

    # --- Time-based leaderboard ---
    range = request.args.get('range', 'today')

    if range == '7days':
        cursor.execute("""
        SELECT 
            u.user_name AS Name, 
            ISNULL(SUM(v.points), 0) AS points
        FROM dbo.users AS u
        LEFT JOIN vw_FamilyLeaderboardWithDates AS v 
            ON u.user_name = v.Name
            AND v.family_id = ?
        AND DATEDIFF(DAY, v.date_awarded, GETDATE()) <= 7
    WHERE u.family_id = ? and not u.role_id = 4
    GROUP BY u.user_name
    Order by points desc                   
    """, (family_id, family_id))

    elif range == 'month':
        cursor.execute("""
        SELECT 
            u.user_name AS Name, 
            ISNULL(SUM(v.points), 0) AS points
        FROM dbo.users AS u
        LEFT JOIN vw_FamilyLeaderboardWithDates AS v 
            ON u.user_name = v.Name
            AND v.family_id = ?
            AND DATEPART(MONTH, v.date_awarded) = DATEPART(MONTH, GETDATE())
            AND DATEPART(YEAR, v.date_awarded) = DATEPART(YEAR, GETDATE())           
        WHERE u.family_id = ? and not u.role_id = 4
        GROUP BY u.user_name
        Order by points desc               
    """, (family_id, family_id))

    else:  # today
        cursor.execute("""
        SELECT 
            u.user_name AS Name, 
            ISNULL(SUM(v.points), 0) AS points
        FROM dbo.users AS u
        LEFT JOIN vw_FamilyLeaderboardWithDates AS v 
            ON u.user_name = v.Name
            AND v.family_id = ?
            AND CAST(v.date_awarded AS DATE) = CAST(GETDATE() AS DATE)           
        WHERE u.family_id = ? and not u.role_id = 4
        GROUP BY u.user_name
        Order by points desc               
    """, (family_id, family_id))


    time_filtered_data = cursor.fetchall()
    conn.close()

    return render_template(
        "leaderboard.html",
        all_time_data=all_time_data,
        time_filtered_data=time_filtered_data,
        selected_range=range
    )



@app.route('/chore_history')
def chore_history():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    family_id = session.get('family_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    from datetime import datetime, timedelta

# If no dates provided, default to last 7 days
    if not start_date or not end_date:
        today = datetime.today().date()
        one_week_ago = today - timedelta(days=7)
    if not start_date:
        start_date = one_week_ago.isoformat()
    if not end_date:
        end_date = today.isoformat()
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Start building the query
    query = """
        SELECT
            u.user_name AS Name,
            c.Chore_name AS Chore,
            a.Date_Complete AS [Completed on],
            a.Points_Earned AS Points
        FROM Chore_assignments AS a
        INNER JOIN Users AS u ON a.assigned_to = u.user_id
        INNER JOIN Chores_list AS c ON a.Chore_ID = c.Chore_id
        WHERE a.Completion_Status = 'complete'
        AND u.family_id = ?
    """

    # Set up parameters with family_id first
    params = [family_id]

    if start_date:
        query += " AND a.Date_Complete >= ?"
        params.append(start_date)

    if end_date:
        query += " AND a.Date_Complete <= ?"
        params.append(end_date)

    query += " ORDER BY [Completed on] DESC"

    # Execute with parameters
    cursor.execute(query, params)
    chores_data = cursor.fetchall()
    conn.close()

    return render_template(
        'chore_history.html',
        chores_data=chores_data,
        start_date=start_date,
        end_date=end_date
    )


@app.route('/active_chores', methods=['GET', 'POST'])
def active_chores():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    family_id = session.get('family_id')
    user_id = session.get('user_id')

    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Chore_Assignments
            SET Completion_Status = 'Submitted',
            Assigned_to = ?           
            WHERE Assignment_ID = ?
        """, (user_id, assignment_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('active_chores'))  # Refresh the page

    # --- Fetch chores ---
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Current user chores
    cursor.execute("""
        SELECT
          u.user_name AS 'Name',
          c.chore_name AS 'Chore',
          a.date_assigned AS 'Set when',
          a.assignment_id,
          a.completion_status as Completion_Status
        FROM Chore_Assignments AS a
        INNER JOIN Users AS u ON a.assigned_to = u.user_id
        INNER JOIN Chores_list AS c ON a.chore_id = c.chore_id
        WHERE a.completion_status != 'Complete'
          and a.completion_status != 'Deleted'
          AND u.family_id = ?
          AND u.user_id = ?
        ORDER BY a.date_assigned DESC
    """, (family_id, user_id))
    
    current_user_chores = cursor.fetchall()
    

    # Other user chores
    cursor.execute("""
        SELECT
          u.user_name AS 'Name',
          c.chore_name AS 'Chore',
          a.date_assigned AS 'Set when',
          a.assignment_id,
          a.completion_status as Completion_Status
        FROM Chore_Assignments AS a
        INNER JOIN Users AS u ON a.assigned_to = u.user_id
        INNER JOIN Chores_list AS c ON a.chore_id = c.chore_id
        WHERE a.completion_status != 'Complete'
        and a.completion_status != 'Deleted'
          AND u.family_id = ?
          AND NOT u.user_id = ?
        ORDER BY a.date_assigned DESC
    """, (family_id, user_id))
    other_user_chores = cursor.fetchall()

    # This is my badge
    cursor.execute("""
        SELECT COUNT(assignment_id) FROM chore_assignments 
        WHERE assigned_to = ? AND completion_status in ('Pending', 'Sent Back')
    """, (user_id,))
    result = cursor.fetchone()
    my_active_chores = result[0] if result else 0
    

    conn.close()
    
    return render_template(
        'Active_chores.html',
        current_user_chores=current_user_chores,
        other_user_chores=other_user_chores,
        active_chores=my_active_chores
    )

@app.route('/chore_assignments', methods=['GET', 'POST'])
def chore_assignments():

    if not session.get('logged_in') or session.get('role_id') not in [1, 2, 3]:
        return redirect(url_for('login'))

    family_id = session.get('family_id')

    if request.method == 'POST':
        assigned_to = int(request.form.get('assigned_to'))
        chore_id = request.form.get('chore_id')
        assigned_by = session.get('user_id')

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Chore_Assignments (
                Chore_ID,
                Assigned_To,
                Assigned_By,
                Date_Assigned,
                Completion_Status
            )
            VALUES (?, ?, ?, GETDATE(), 'Pending')
        """, (chore_id, assigned_to, assigned_by))
        conn.commit()
        conn.close()

        # ✅ Redirect with selected values in query string
        return redirect(url_for('chore_assignments', selected_user=assigned_to, selected_chore=chore_id))

    # ✅ Pull the selection from query params
    selected_user = request.args.get('selected_user', type=int)
    selected_chore = request.args.get('selected_chore', type=int)

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("SELECT user_name, user_id FROM users WHERE family_id = ?", (family_id,))
    users = cursor.fetchall()

    cursor.execute("SELECT chore_name, chore_id FROM chores_list WHERE family_id IN (2, ?) and is_active = 1 ORDER BY chore_name ASC", (family_id,))
    chores = cursor.fetchall()

    conn.close()

    # ✅ Pass selected values to the template
    return render_template(
        'chore_assignments.html',
        users=users,
        chores=chores,
        selected_user=selected_user,
        selected_chore=selected_chore
    )


@app.route('/chore_completions', methods=['GET', 'POST'])
def chore_completions():
    if not session.get('logged_in') or session.get('role_id') != 1:
        return redirect(url_for('login'))

    family_id = session.get('family_id')

    if request.method == 'POST':
        action = request.form.get('action')

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        if action == 'approve_all':
    # Get all submitted chores for this family
            cursor.execute("""
        SELECT c.assignment_id, c.assigned_to
        FROM Chore_Assignments as c
        Inner join users as u
        on c.assigned_to = u.user_id
        WHERE family_id = ? AND c.completion_status = 'Submitted'
    """, (family_id,))
            assignments = cursor.fetchall()

            for assignment_id, assigned_to in assignments:
                cursor.execute("""
            UPDATE Chore_Assignments
            SET completion_status = 'Complete',
                date_complete = GETDATE(),
                completed_by = ?
            WHERE assignment_id = ?
        """, (assigned_to, assignment_id))

        else:
            assignment_id = request.form.get('assignment_id')

            if action == 'approve':
            # Grab current Assigned_To user_id before update
                cursor.execute("SELECT assigned_to FROM Chore_Assignments WHERE assignment_id = ?", (assignment_id,))
                result = cursor.fetchone()
                if result:
                    assigned_to = result[0]
                    cursor.execute("""
                    UPDATE Chore_Assignments
                    SET completion_status = 'Complete',
                        date_complete = GETDATE(),
                        completed_by = ?
                    WHERE assignment_id = ?
                """, (assigned_to, assignment_id))

            elif action == 'send_back':
                cursor.execute("""
                UPDATE Chore_Assignments
                SET completion_status = 'Sent Back'
                WHERE assignment_id = ?
            """, (assignment_id,))
                
            elif action == 'delete':
                cursor.execute("""
                UPDATE Chore_Assignments
                SET completion_status = 'Deleted'
                WHERE assignment_id = ?
            """, (assignment_id,))    

        conn.commit()
        conn.close()
        return redirect(url_for('chore_completions'))

    # Get submitted chores
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
          u.user_name AS 'Name',
          c.chore_name AS 'Chore',
          a.date_assigned AS 'Set when',
          a.assignment_id,
          a.completion_status as Completion_Status
        FROM Chore_Assignments AS a
        INNER JOIN Users AS u ON a.assigned_to = u.user_id
        INNER JOIN Chores_list AS c ON a.chore_id = c.chore_id
        WHERE a.completion_status = 'Submitted'
          AND u.family_id = ?
        ORDER BY a.date_assigned DESC
    """, (family_id))
    
    Submitted_chores = cursor.fetchall()
    
    conn.close()


    return render_template(
        'chore_completions.html',
        Submitted_chores=Submitted_chores
    )

@app.route('/user_settings', methods=['GET', 'POST'])
def user_settings():
    if not session.get('logged_in') or session.get('role_id') != 1:
        return redirect(url_for('login'))

    family_id = session.get('family_id')
    user_id = session.get('user_id')
    
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'New_user':
            username = request.form.get('username')
            email = request.form.get('email')
            role_id = request.form.get('role')
            is_active = 1 if request.form.get('active') else 0

            cursor.execute("""
                INSERT INTO users (user_name, role_id, family_id, date_created, is_active, email)
                VALUES (?, ?, ?, GETDATE(), ?, ?)
            """, (username, role_id, family_id, is_active, email))

        elif action == 'Chore_name':
            Chore_name = request.form.get('Chore_name')
            cursor.execute("""
                INSERT INTO Chores_list (Chore_name, is_Active, Date_created, created_by, family_id)
                VALUES (?, 1, GETDATE(), ?, ?)
            """, (Chore_name, user_id, family_id))

        elif action == 'Update_user':
            user_id = int(request.form.get('user_id'))
            username = request.form.get('username')
            email = request.form.get('email')
            role_id = int(request.form.get('role_id'))
            is_active = int(request.form.get('is_active'))
            current_user_id = session.get('user_id')

            # === Self-protection ===
            if user_id == current_user_id:
                if role_id != 1:
                    flash("You cannot remove your own admin rights.", "error")
                    conn.close()
                    return redirect('/user_settings')
                if is_active == 0:
                    flash("You cannot deactivate your own account.", "error")
                    conn.close()
                    return redirect('/user_settings')

                # === Admin redundancy check ===
            if role_id != 1 or is_active == 0:
                cursor.execute("""
                    SELECT COUNT(*) FROM users
                    WHERE role_id = 1 AND is_active = 1 AND family_id = ?
                """, (session.get('family_id'),))
                admin_count = cursor.fetchone()[0]

                if admin_count <= 1 and user_id == current_user_id:
                    flash("There must be at least one active admin. You cannot remove yourself.", "error")
                    conn.close()
                    return redirect('/user_settings')

    # === Perform update ===
            cursor.execute("""
                UPDATE users
                SET user_name = ?, email = ?, role_id = ?, is_active = ?
                WHERE user_id = ?
            """, (username, email, role_id, is_active, user_id))

        elif action == 'Update_chore':
            chore_id = request.form.get('chore_id')
            chore_name = request.form.get('chore_name')
            is_active = request.form.get('is_active')

            cursor.execute("""
                UPDATE Chores_list
                SET Chore_name = ?, Is_active = ?
                WHERE chore_id = ?
            """, (chore_name, is_active, chore_id))

        conn.commit()
        conn.close()
        return redirect('/user_settings')

    # === Fetch Updated Data === #
    cursor.execute("""
        SELECT u.user_id,
               u.user_name as 'User Name',
               r.role_name as 'Current Role',
               u.email as email,
               CASE WHEN u.is_active = 1 THEN 'Yes' ELSE 'No' END as 'Are they still active?'
        FROM users AS u
        INNER JOIN roles AS r ON u.role_id = r.role_id
        WHERE family_id = ?
    """, (family_id,))
    current_users_per_family = cursor.fetchall()

    cursor.execute("""
        SELECT chore_id,
               Chore_name as 'chore',
               CASE WHEN Is_active = 1 THEN 'yes' ELSE 'no' END as 'live'
        FROM Chores_list
        WHERE Family_id = ?
    """, (family_id,))
    family_chores = cursor.fetchall()

    conn.close()

    return render_template(
        "user_settings.html",
        current_users_per_family=current_users_per_family,
        family_chores=family_chores
    )

@app.route('/family_settings', methods=['GET', 'POST'])
def family_settings():
    if not session.get('logged_in') or session.get('role_id') != 1:
        return redirect(url_for('login'))

    family_id = session.get('family_id')
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Handle form submission for changing name
    if request.method == 'POST':
        if 'new_family_name' in request.form:
            new_name = request.form['new_family_name']
            cursor.execute("""
                UPDATE Families
                SET family_name = ?
                WHERE family_id = ?
            """, (new_name, family_id))
            conn.commit()
            flash("Family name updated.", "success")
        elif 'deactivate' in request.form:
            # Deactivate family and all users
            cursor.execute("UPDATE Families SET is_active = 0 WHERE family_id = ?", (family_id,))
            cursor.execute("UPDATE Users SET is_active = 0 WHERE family_id = ?", (family_id,))
            conn.commit()
            conn.close()
            session.clear()
            flash("Account deactivated. You have been logged out.", "warning")
            return redirect(url_for('login'))

    # Get current family info
    cursor.execute("""
        SELECT family_name,
               CASE WHEN is_active = 1 THEN 'Yes' ELSE 'No' END AS active
        FROM Families
        WHERE family_id = ?
    """, (family_id,))
    family_info = cursor.fetchall()
    conn.close()

    return render_template("family_settings.html", family_info=family_info)

@app.route('/logout')
def logout():
    log_event(session.get('username'), 'Logout')
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


