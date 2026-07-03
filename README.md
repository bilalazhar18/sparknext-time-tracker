# SparkNext Time Tracker ⏱️

<div align="center">
  <img src="static/images/logo.png" alt="SparkNext Logo" width="300">
</div>

SparkNext Time Tracker is a robust, highly-secure, and fully mobile-responsive employee attendance management system. It leverages real-time GPS tracking and dynamic QR code generation to strictly enforce location-based attendance, completely preventing remote check-ins or unauthorized time logging.

## 🌟 Key Features

* **Smart Kiosk Portal:** An automated landing page (`/`) designed to be displayed on tablets/monitors at building entrances. It automatically detects its physical location via GPS, identifies the nearest active building, and generates a dynamic QR code for employees to scan.
  
  <div align="center">
    <img src="static/images/qr.png" alt="QR Code Kiosk" width="200">
  </div>

* **Strict Geofencing (100-Meter Radius):** Employees are strictly prohibited from logging in, registering, or checking in unless their personal device verifies they are within a 100-meter radius of their assigned building.
* **Anti-Spoofing & Security:** The system prevents duplicate attendance logs, blocks registration without physical QR scanning, and denies employee login if location services are disabled.
* **Mobile-Responsive UI:** Built with a professional Bootstrap-powered dashboard template, ensuring seamless usability across desktops, tablets, and smartphones. Includes intelligently prioritized data tables that adapt to screen sizes, dynamic sidebar navigation, global flash messaging, and auto-updating components like the footer year.
* **Admin Dashboard:** A centralized portal for administrators to manage buildings, employee shifts, and monitor daily attendance logs (Admins are exempt from location restrictions).
* **Building Management Module:** Admins can seamlessly add, edit, and deactivate buildings directly from the dashboard. Adding a new building securely auto-generates its unique QR code and allows optional generation of standard shifts (Morning/Evening) for immediate deployment.

## 🛠️ Technology Stack

This application was developed using a modern, scalable Python stack:
* **Backend:** [Flask](https://flask.palletsprojects.com/) (Python)
* **Database & ORM:** MySQL, handled via [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
* **Database Migrations:** [Flask-Migrate](https://flask-migrate.readthedocs.io/)
* **Frontend:** HTML5, CSS3, JavaScript, [Bootstrap 5](https://getbootstrap.com/), and Jinja2 templating
* **Deployment Ready:** Configured for cPanel/Phusion Passenger deployment via `passenger_wsgi.py`

## 🚀 Installation & Setup

Follow these steps to run the application locally for development:

### 1. Prerequisites
Ensure you have Python 3.8+ and MySQL Server installed on your machine.

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd time_tracker
```

### 3. Create a Virtual Environment & Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure the Database
Open `config.py` and update the `SQLALCHEMY_DATABASE_URI` to point to your local MySQL database. 
*Example:* `mysql+pymysql://username:password@localhost/database_name`

### 5. Seed the Database
Run the seeder script to populate the database with initial required data (like the Admin account and test buildings):
```bash
python seeder.py
```

### 6. Run the Application
Start the Flask development server:
```bash
python run.py
```
The application will now be running at `http://127.0.0.1:5000/`. 

## 📖 Usage Guide

1. **Start the Kiosk:** Open the root URL (`/`) on a device located at the building. Allow location access so it can display the correct QR code.
2. **Employee Registration:** A new employee scans the QR code with their smartphone, which securely routes them to the registration page.
3. **Attendance Logging:** Once registered and logged in, employees simply tap **Check In** on their dashboard while inside the building to log their attendance.

## 🛡️ Security Notes
* Ensure the application is served over **HTTPS** in production. Modern web browsers strictly require HTTPS to allow access to the Geolocation API (`navigator.geolocation`).
* Keep your `SECRET_KEY` in `config.py` securely stored in environment variables for production environments.
