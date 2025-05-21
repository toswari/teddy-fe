from flask import Flask, render_template, send_file, make_response, jsonify
import os
import platform
import psutil
import socket
import json
import datetime
import io
import sys

# Try to import optional modules with fallbacks
try:
    import cpuinfo
    cpu_info_available = True
except ImportError:
    cpu_info_available = False

try:
    import GPUtil
    gpu_available = True
except ImportError:
    gpu_available = False

# Try to import PDF generation modules
try:
    from xhtml2pdf import pisa
    pdf_generation_available = True
except ImportError:
    pdf_generation_available = False

app = Flask(__name__)

def get_system_info():
    """Gather system resource information"""
    # Operating System
    os_info = {
        "system": platform.system(),
        "version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine()
    }
    
    # CPU Information
    if cpu_info_available:
        try:
            cpu_info = cpuinfo.get_cpu_info()
            cpu_data = {
                "brand": cpu_info.get('brand_raw', 'Not available'),
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "frequency": f"{psutil.cpu_freq().current:.2f} MHz" if psutil.cpu_freq() else "Not available"
            }
        except Exception as e:
            cpu_data = {
                "brand": "Not available (Error: {})".format(str(e)),
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "frequency": "Not available"
            }
    else:
        cpu_data = {
            "brand": "Not available (cpuinfo module not installed)",
            "cores_logical": psutil.cpu_count(logical=True),
            "cores_physical": psutil.cpu_count(logical=False),
            "frequency": f"{psutil.cpu_freq().current:.2f} MHz" if psutil.cpu_freq() else "Not available"
        }
    
    # Memory Information
    memory = psutil.virtual_memory()
    memory_data = {
        "total": f"{memory.total / (1024 ** 3):.2f} GB",
        "available": f"{memory.available / (1024 ** 3):.2f} GB",
        "used": f"{memory.used / (1024 ** 3):.2f} GB",
        "percent": f"{memory.percent}%"
    }
    
    # Storage Information
    storage_data = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            partition_data = {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "filesystem": partition.fstype,
                "total": f"{usage.total / (1024 ** 3):.2f} GB",
                "used": f"{usage.used / (1024 ** 3):.2f} GB",
                "free": f"{usage.free / (1024 ** 3):.2f} GB",
                "percent": f"{usage.percent}%"
            }
            storage_data.append(partition_data)
        except (PermissionError, FileNotFoundError):
            # Skip partitions we can't access
            continue
    
    # GPU Information
    gpu_data = []
    if gpu_available:
        try:
            gpus = GPUtil.getGPUs()
            for i, gpu in enumerate(gpus):
                gpu_info = {
                    "id": i,
                    "name": gpu.name,
                    "load": f"{gpu.load * 100:.2f}%",
                    "memory_total": f"{gpu.memoryTotal:.2f} MB",
                    "memory_used": f"{gpu.memoryUsed:.2f} MB",
                    "memory_free": f"{gpu.memoryFree:.2f} MB",
                    "temperature": f"{gpu.temperature}°C",
                    "driver": "Not available" # GPUtil doesn't provide driver info
                }
                gpu_data.append(gpu_info)
        except Exception as e:
            gpu_data = [{
                "id": 0,
                "name": f"Error detecting GPU: {str(e)}",
                "load": "N/A",
                "memory_total": "N/A",
                "memory_used": "N/A",
                "memory_free": "N/A",
                "temperature": "N/A",
                "driver": "N/A"
            }]
    
    # Network Information
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "Not available"
    
    network_data = {
        "hostname": hostname,
        "ip_address": ip_address
    }
    
    # Current Time
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Python Information
    python_data = {
        "version": sys.version,
        "path": sys.executable
    }
    
    # Combine all data
    all_info = {
        "os": os_info,
        "cpu": cpu_data,
        "memory": memory_data,
        "storage": storage_data,
        "gpu": gpu_data,
        "network": network_data,
        "python": python_data,
        "timestamp": current_time
    }
    
    return all_info

def generate_pdf_report(data):
    """Generate PDF report from system data"""
    if not pdf_generation_available:
        return None
        
    # HTML content for PDF
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>System Resource Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                color: #333;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .logo {{
                max-width: 200px;
                margin-bottom: 10px;
            }}
            h1, h2, h3 {{
                color: #0052CC;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>System Resource Report</h1>
            <p>Generated: {data['timestamp']}</p>
        </div>
        
        <div class="section">
            <h2>Operating System</h2>
            <table>
                <tr><th>System</th><td>{data['os']['system']}</td></tr>
                <tr><th>Version</th><td>{data['os']['version']}</td></tr>
                <tr><th>Platform</th><td>{data['os']['platform']}</td></tr>
                <tr><th>Architecture</th><td>{data['os']['machine']}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>CPU Information</h2>
            <table>
                <tr><th>Model</th><td>{data['cpu']['brand']}</td></tr>
                <tr><th>Physical Cores</th><td>{data['cpu']['cores_physical']}</td></tr>
                <tr><th>Logical Cores</th><td>{data['cpu']['cores_logical']}</td></tr>
                <tr><th>Frequency</th><td>{data['cpu']['frequency']}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Memory Information</h2>
            <table>
                <tr><th>Total</th><td>{data['memory']['total']}</td></tr>
                <tr><th>Available</th><td>{data['memory']['available']}</td></tr>
                <tr><th>Used</th><td>{data['memory']['used']}</td></tr>
                <tr><th>Usage</th><td>{data['memory']['percent']}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Storage Information</h2>
            <table>
                <tr>
                    <th>Device</th>
                    <th>Mountpoint</th>
                    <th>Filesystem</th>
                    <th>Total</th>
                    <th>Used</th>
                    <th>Free</th>
                    <th>Usage</th>
                </tr>
    """
    
    # Add storage data rows
    for storage in data['storage']:
        html_content += f"""
                <tr>
                    <td>{storage['device']}</td>
                    <td>{storage['mountpoint']}</td>
                    <td>{storage['filesystem']}</td>
                    <td>{storage['total']}</td>
                    <td>{storage['used']}</td>
                    <td>{storage['free']}</td>
                    <td>{storage['percent']}</td>
                </tr>
        """
    
    html_content += """
            </table>
        </div>
    """
    
    # Add GPU section if available
    if data['gpu']:
        html_content += """
        <div class="section">
            <h2>GPU Information</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Load</th>
                    <th>Total Memory</th>
                    <th>Used Memory</th>
                    <th>Free Memory</th>
                    <th>Temperature</th>
                </tr>
        """
        
        for gpu in data['gpu']:
            html_content += f"""
                <tr>
                    <td>{gpu['id']}</td>
                    <td>{gpu['name']}</td>
                    <td>{gpu['load']}</td>
                    <td>{gpu['memory_total']}</td>
                    <td>{gpu['memory_used']}</td>
                    <td>{gpu['memory_free']}</td>
                    <td>{gpu['temperature']}</td>
                </tr>
            """
            
        html_content += """
            </table>
        </div>
        """
    else:
        html_content += """
        <div class="section">
            <h2>GPU Information</h2>
            <p>No GPU detected or GPU information not available.</p>
        </div>
        """
    
    # Network and footer
    html_content += f"""
        <div class="section">
            <h2>Network Information</h2>
            <table>
                <tr><th>Hostname</th><td>{data['network']['hostname']}</td></tr>
                <tr><th>IP Address</th><td>{data['network']['ip_address']}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Python Information</h2>
            <table>
                <tr><th>Version</th><td>{data['python']['version']}</td></tr>
                <tr><th>Path</th><td>{data['python']['path']}</td></tr>
            </table>
        </div>
        
        <div class="footer">
            <p>This report was automatically generated on {data['timestamp']}.</p>
            <p>Clarifai System Resources Report</p>
        </div>
    </body>
    </html>
    """
    
    try:
        # Create PDF
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        # Return PDF if successful
        if pisa_status.err:
            return None
        
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

@app.route('/')
def index():
    """Home page with system resource information"""
    system_data = get_system_info()
    return render_template('index.html', data=system_data)

@app.route('/download-report')
def download_report():
    """Generate and download PDF report"""
    system_data = get_system_info()
    
    if not pdf_generation_available:
        return jsonify({
            "error": "PDF generation libraries not available",
            "message": "The required libraries for PDF generation (xhtml2pdf) are not installed."
        }), 500
    
    pdf_buffer = generate_pdf_report(system_data)
    
    if pdf_buffer is None:
        return jsonify({
            "error": "PDF generation failed",
            "message": "An error occurred while generating the PDF report."
        }), 500
    
    # Generate filename with timestamp
    filename = f"system_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Create response with PDF
    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

@app.route('/api/system-info')
def api_system_info():
    """API endpoint to get system info as JSON"""
    system_data = get_system_info()
    return jsonify(system_data)

if __name__ == '__main__':
    # Create logo directory if it doesn't exist
    os.makedirs('static/img', exist_ok=True)
    
    # Check for PDF generation capability
    if not pdf_generation_available:
        print("WARNING: PDF generation libraries not available. PDF download will not work.")
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)