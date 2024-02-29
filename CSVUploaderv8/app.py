from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename 
import os
import csv
import json
import time
from datetime import datetime
from clarifai.client.input import Inputs
from clarifai.client.user import User
from clarifai.client.dataset import Dataset
from clarifai.client.app import App as clarifaiapp

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'png', 'jpg', 'jpeg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = b'mulder@clarifai.com'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No CSV file part')
            return redirect(request.url)
        csv_file = request.files['csv_file']
        if csv_file.filename == '':
            flash('No selected CSV file')
            return redirect(request.url)
        if csv_file and allowed_file(csv_file.filename):
            csv_filename = secure_filename(csv_file.filename)
            csv_file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            csv_file.save(csv_file_path)
            csv_file.seek(0)
            csv_file.read()
            flash('CSV file uploaded successfully')
            for image_file in request.files.getlist('image_files'):
                if image_file and allowed_file(image_file.filename):
                    image_filename = secure_filename(image_file.filename)
                    image_file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    image_file.save(image_file_path)
                    flash(f'{image_filename} file uploaded successfully')
                else:
                    flash(f'Invalid image file: {image_file.filename}')
            flash('All Image files uploaded successfully')
            return redirect(url_for('select_fields', filename=csv_filename))
        else:
            flash('Invalid file type')
            return redirect(request.url)
    return render_template('index.html')

@app.route('/select_fields/<filename>', methods=['GET', 'POST'])
def select_fields(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if request.method == 'POST':
        base_url = request.form['base_url']
        id_field = request.form['id_field']
        path_field = request.form['path_field']
        user_id = request.form['user_id']
        pat = request.form['pat']
        dataset_id = "."#request.form['dataset_id']
        app_id = request.form['app_id']
        description = "."#request.form['description_field']
        return redirect(url_for('process_upload', filename=filename, id_field=id_field, path_field=path_field,
                                user_id=user_id, pat=pat, dataset_id=dataset_id, app_id=app_id, base_url=base_url, description=description))

    try:
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            field_names = next(reader)
    except FileNotFoundError:
        flash('The uploaded CSV file is not found.')
        return redirect(url_for('index')) 
    except StopIteration:
        flash('The uploaded CSV file is empty or does not contain valid data.')
        return redirect(url_for('index')) 
    return render_template('select_fields.html', filename=filename, field_names=field_names)

import math

@app.route('/process_upload/<filename>', methods=['POST'])
def process_upload(filename):
    id_field = request.form['id_field']
    path_field = request.form['path_field']
    base_url = request.form['base_url']
    user_id = request.form['user_id']
    pat = request.form['pat']
    dataset_id = "." 
    app_id = request.form['app_id']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    input_data = []
    input_ids = []
    with open(file_path, mode='r', newline='') as input_file:
        reader = csv.DictReader(input_file)
        for row in reader:
            input_id = row.pop(id_field)
            input_ids.append(str(input_id))
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(row.pop(path_field).replace('\\', '/')))
            metadata = {key: value for key, value in row.items()}
            input_data.append((input_id, input_path, metadata))
    chunk_size = 10
    num_chunks = math.ceil(len(input_data) / chunk_size)
    for i in range(num_chunks):
        chunk = input_data[i * chunk_size : (i + 1) * chunk_size]
        formatted_csv = os.path.join(app.config['UPLOAD_FOLDER'], f'formatted_{i}.csv')
        with open(formatted_csv, mode='w', newline='') as output_file:
            writer = csv.writer(output_file)
            writer.writerow(['inputid', 'input', 'concepts', 'metadata', 'geopoints'])
            for input_id, input_path, metadata in chunk:
                writer.writerow([input_id, input_path, '', json.dumps(metadata), ''])
        appv = User(user_id=user_id, pat=pat, base_url=base_url).app(app_id=app_id)
        input_obj = appv.inputs()
        inputs = input_obj.get_inputs_from_csv(
            csv_path=formatted_csv,
            input_type='image',
            csv_type='file_path',
        )
        input_obj.upload_inputs(inputs=inputs, show_log=True)
        flash(f'Uploaded batch {i+1} of {num_chunks}...')
        print(f'Uploaded batch {i+1} of {num_chunks}...')
    
    input_obj = User(user_id=user_id, pat=pat, base_url=base_url).app(app_id=app_id).inputs()
    all_inputs = list(input_obj.list_inputs(input_type='image'))
    ids = []
    completed_ids = []
    for itema in all_inputs:
        if str(itema.id) not in ids:
            ids.append(str(itema.id))
    for itemb in ids:
        if str(itemb) in input_ids:
            input_ids.remove(str(itemb))
            if str(itemb) not in completed_ids:
                completed_ids.append(str(itemb))
    session['failed_ids'] = input_ids 
    session['completed_ids'] = completed_ids  
    return redirect(url_for('success'))

@app.route('/success')
def success():
    return render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=5000, host='0.0.0.0', use_reloader=False)
