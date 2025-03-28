import ssl
import socket
from urllib.parse import urlparse


URL = "web-staging.clarifai.com"  # The server URL
PORT = 443                    # The port to connect to
OUTPUT_FILE = "staging_server_cert.pem"  # The file to save the certificate to

def get_server_certificate(url, port, output_file):
    url = url.replace("https://", "").replace("http://", "")
    url = url.split('/')[0]
    hostname = url
    if not hostname:
        raise ValueError("Invalid URL or hostname not provided.")
    print(f"Connecting to {hostname}:{port} to retrieve certificate...")
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            # Get the certificate in DER format
            cert_der = ssock.getpeercert(binary_form=True)
            # Convert DER to PEM format
            cert_pem = ssl.DER_cert_to_PEM_cert(cert_der)
    with open(output_file, 'w') as f:
        f.write(cert_pem)
    print("Certificate retrieved successfully.")
    print(cert_pem)
    print(f"Certificate saved to {output_file}")

def main():
    try:
        get_server_certificate(URL, PORT, OUTPUT_FILE)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
