import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from flask import Flask, render_template, request, redirect, flash, session, make_response
import sqlite3
from werkzeug.utils import secure_filename
from PIL import Image
import os
import base64



app = Flask(__name__)
app.secret_key = "123"  

cnn_model = load_model('model_cnn.h5')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    

def init_db():
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()

        

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doctor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                specialization TEXT NOT NULL,
                experience INTEGER NOT NULL,
                clinic_address TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patient (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                age INTEGER NOT NULL,
                status TEXT NOT NULL,
                image BLOB,
                doctor_id INTEGER,
                FOREIGN KEY (doctor_id) REFERENCES doctor(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(doctor_id, patient_id),
                FOREIGN KEY (doctor_id) REFERENCES doctor(id),
                FOREIGN KEY (patient_id) REFERENCES patient(id)
            )
        ''')

init_db()


@app.template_filter('b64encode')
def b64encode_filter(data):
    if data:
        return base64.b64encode(data).decode('utf-8')
    return ''

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/doctor')
def doctor():
    return render_template('doctor.html')

@app.route('/doctor_register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        doctor_name = request.form['doctor_name']
        doctor_email = request.form['doctor_email']
        specialization = request.form['specialization']
        experience = request.form['experience']
        clinic_address = request.form['clinic_address']
        password = request.form['password']

        try:
            with sqlite3.connect('hospital.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO doctor (name, email, specialization, experience, clinic_address, password)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (doctor_name, doctor_email, specialization, experience, clinic_address, password))
                conn.commit()
            flash('Doctor registered successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.', 'danger')

        return redirect('/doctor_login')
    return render_template('doctor.html')

@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect('hospital.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT * FROM doctor WHERE email = ? AND password = ?''', (email, password))
            doctor = cursor.fetchone()

        if doctor:
            session['doctor_id'] = doctor[0]  
            session['doctor_name'] = doctor[1]  
            flash('Login successful!', 'success')
            return redirect('/doctor_dashboard')
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('doctor_login.html')

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'doctor_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect('/doctor_login')
    return render_template('doctor_dashboard.html', doctor_name=session.get('doctor_name', 'Doctor'))


@app.route('/patient')
def patient():
    return render_template('patient.html')

@app.route('/patient_register', methods=['GET', 'POST'])
def patient_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        age = request.form['age']
        status = request.form['status']
        image_file = request.files['image']

        if image_file:
            image_blob = image_file.read()
        else:
            image_blob = None

        try:
            with sqlite3.connect('hospital.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO patient (name, email, password, phone, address, age,status, image)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, email, password, phone, address, age, status,image_blob))
                conn.commit()
            flash('Patient registered successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.', 'danger')

        return redirect('/patient_register')
    return render_template('patient.html')

@app.route('/patient_login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect('hospital.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT id, name FROM patient WHERE email = ? AND password = ?''', (email, password))
            patient = cursor.fetchone()

        if patient:
            session['patient_id'] = patient[0]  
            session['patient_name'] = patient[1]  
            flash('Login successful!', 'success')
            return redirect('/patient_dashboard')
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('patient_login.html')


@app.route('/patient_dashboard')
def patient_dashboard():
    if 'patient_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect('/patient_login')
    
    patient_name = session.get('patient_name', 'Patient')
    return render_template('patient_dashboard.html', patient_name=patient_name)


def preprocess_image(image_path):
    img = Image.open(image_path).convert('RGB')
    img_resized = img.resize((256, 256))  # Resize to the correct dimensions
    img_array = img_to_array(img_resized) / 255.0  # Normalize pixel values
    return img_array

@app.route('/upload_image')
def upload_image():
    return render_template('upload_image.html')

@app.route('/predict', methods=['POST'])
def predict():
    # Mapping numeric predictions to class names
    class_labels = {
        0: "Benign",
        1: "Malignant",
        2: "Normal"
    }

    if 'file' not in request.files:
        flash('No file part.', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        img_path = os.path.join('static/uploads', filename)
        file.save(img_path)

        # Preprocess the image to match the model input size
        processed_image = preprocess_image(img_path).reshape(1, 256, 256, 3)  # Adjust based on your model's input size
        
        # Predict using the model
        prediction = cnn_model.predict(processed_image)
        predicted_class = prediction.argmax(axis=1)[0]  # Get the predicted class index
        
        # Get the class name from the mapping
        predicted_label = class_labels.get(predicted_class, "Unknown")

        return render_template('result.html', prediction=predicted_label, image_path=img_path)

    flash('Invalid file format.', 'danger')
    return redirect(request.url)



@app.route('/result')
def result():
    prediction = request.args.get('prediction', 'No result')
    return render_template('result.html', prediction=prediction)

@app.route('/image')
def image():
    return render_template('image.html')

@app.route('/check_image/<int:patient_id>', methods=['GET'])
def check_image(patient_id):
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT image FROM patient WHERE id = ?', (patient_id,))
        patient_image = cursor.fetchone()
        
        if patient_image and patient_image[0]:
            img_path = os.path.join('uploads', f"patient_{patient_id}.jpg")
            
            with open(img_path, 'wb') as f:
                f.write(patient_image[0])
            
            processed_image = preprocess_image(img_path)
            processed_image = processed_image.reshape(1, 256, 256, 3)  # Add batch dimension
            
            prediction = cnn_model.predict(processed_image)
            predicted_class = prediction.argmax(axis=1)[0]  # Get predicted class index
            
            # Map prediction to class names
            class_labels = {0: "Benign", 1: "Malignant", 2: "Normal"}
            predicted_label = class_labels.get(predicted_class, "Unknown")
            
            return render_template('update.html', prediction=predicted_label, image_path=img_path)
        else:
            return f"No image found for patient ID {patient_id}", 404

@app.route('/update')
def update():
    prediction = request.args.get('prediction', 'No result')
    return render_template('update.html', prediction=prediction)

@app.route('/patient_details')
def patient_details():
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, phone, address, age, status, image FROM patient')
        patients = cursor.fetchall()
    
    return render_template('patient_details.html', patients=patients)

@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    if request.method == 'POST':
        status = request.form['status']
        doctor_id = request.form['doctor_id']

        with sqlite3.connect('hospital.db') as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE patient
                SET status = ?, doctor_id = ?
                WHERE id = ?
            ''', (status, doctor_id, patient_id))
            conn.commit()

            cursor.execute('''
                INSERT INTO attendances (doctor_id, patient_id)
                VALUES (?, ?)
                ON CONFLICT (doctor_id, patient_id) 
                DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            ''', (doctor_id, patient_id))
            conn.commit()

        flash('Patient details updated successfully!', 'success')
        return redirect('/patient_details')

    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, phone, address, age, status, doctor_id FROM patient WHERE id = ?', (patient_id,))
        patient = cursor.fetchone()

        cursor.execute('SELECT id, name FROM doctor')
        doctors = cursor.fetchall()

    if not patient:
        flash('Patient not found.', 'danger')
        return redirect('/patient_details')

    return render_template('edit_patient.html', patient=patient, doctors=doctors)

@app.route('/download_image/<int:patient_id>')
def download_image(patient_id):
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT image, name FROM patient WHERE id = ?', (patient_id,))
        patient = cursor.fetchone()

    if patient and patient[0]:
        image_data = patient[0]
        response = make_response(image_data)
        response.headers['Content-Type'] = 'image/jpeg'
        response.headers['Content-Disposition'] = f'attachment; filename={patient[1]}_image.jpg'
        return response
    else:
        flash('Image not found for this patient.', 'danger')
        return redirect('/patient_details')

@app.route('/view_status')
def view_status():
    patient_id = session.get('patient_id')
    if not patient_id:
        flash('You must be logged in to view your status.', 'danger')
        return redirect('/patient_login')
    
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                a.id AS attendance_id,
                p.name AS patient_name,
                d.name AS doctor_name,
                p.status AS patient_status
            FROM attendances a
            JOIN doctor d ON a.doctor_id = d.id
            JOIN patient p ON a.patient_id = p.id
            WHERE p.id = ?
        ''', (patient_id,))
        details = cursor.fetchone()

    if details:
        return render_template('view_status.html', details=details)
    else:
        flash('No attendance records found for this patient.', 'danger')
        return redirect('/patient_dashboard')

@app.route('/attend_doctor', methods=['GET'])
def attend_doctor():
    with sqlite3.connect('hospital.db') as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                a.id,
                d.name AS doctor_name,
                p.name AS patient_name,
                p.status,
                a.updated_at
            FROM attendances a
            JOIN doctor d ON a.doctor_id = d.id
            JOIN patient p ON a.patient_id = p.id
        ''')
        associations = cursor.fetchall()

    return render_template('attend_doctor.html', associations=associations)





if __name__ == '__main__':
    app.run(debug=False, port=700)
