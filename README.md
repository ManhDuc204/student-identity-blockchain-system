# 🎓 Student Flask Blockchain System

A secure blockchain-based student identity verification system built with Flask, Solidity, Ethereum, and Web3.py.

---

# 📌 Project Overview

This project is designed to verify and manage student identities using Blockchain technology.
The system stores student verification hashes on Ethereum blockchain to ensure:

* Data integrity
* Tamper resistance
* Secure authentication
* Transparent verification

The application provides a web dashboard where administrators can:

* Add students
* Verify student information
* Track blockchain transactions
* Generate QR verification
* Export reports

---

# 🚀 Main Features

✅ Student Identity Registration
✅ Blockchain Hash Storage
✅ Ethereum Smart Contract Integration
✅ QR Code Generation
✅ PDF Export
✅ Student Verification System
✅ Admin Authentication
✅ Transaction Logging
✅ Dashboard Statistics
✅ Tamper-Proof Verification

---

# 🛠️ Technologies Used

| Technology          | Description             |
| ------------------- | ----------------------- |
| Flask               | Python Web Framework    |
| Solidity            | Smart Contract Language |
| Ethereum / Ganache  | Blockchain Network      |
| Web3.py             | Blockchain Interaction  |
| SQLAlchemy          | Database ORM            |
| HTML/CSS/JavaScript | Frontend                |
| Bootstrap           | UI Framework            |

---

# 📂 Project Structure

```bash
student-flask-blockchain/
│
├── blockchain/
│   ├── build/contracts/
│   │   └── StudentIdentity.json
│   │
│   ├── contracts/
│   │   └── StudentIdentity.sol
│
├── database/
│   └── student.db
│
├── flask_session/
│
├── migrations/
│
├── static/
│
├── templates/
│   ├── add_student.html
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── students.html
│   ├── tx_logs.html
│   └── verify.html
│
├── utils/
│
├── app.py
├── debug_contract.py
├── debug_env.py
├── env.example
├── migrate_db.py
├── repair_artifact.py
├── requirements.txt
├── test_blockchain.py
├── test_tx_add_student.py
├── TODO.md
└── truffle-config.js
```

---

# ⚙️ System Architecture

```text
+----------------------+
|    Web Interface     |
| HTML/CSS/Bootstrap   |
+----------+-----------+
           |
           v
+----------------------+
|     Flask Backend    |
| Authentication/API   |
+----------+-----------+
           |
           v
+----------------------+
|       Web3.py        |
| Blockchain Connector |
+----------+-----------+
           |
           v
+----------------------+
| Ethereum Blockchain  |
| Smart Contract Layer |
+----------------------+
```

---

# 🔗 Blockchain Workflow

1️⃣ Admin adds student information
2️⃣ System generates SHA-256 hash
3️⃣ Hash is sent to Smart Contract
4️⃣ Ethereum stores immutable record
5️⃣ Verification compares database hash with blockchain hash
6️⃣ Matching hash = Valid identity

---

# 🔒 Security Features

* SHA-256 hashing
* Immutable blockchain storage
* Secure admin login
* Transaction verification
* Blockchain receipt validation
* Session management

---

# 🧠 Smart Contract

The Solidity smart contract handles:

* Adding student hashes
* Retrieving stored hashes
* Verifying authenticity
* Managing blockchain transactions

Example:

```solidity
function addStudent(
    string memory studentId,
    string memory studentHash
) public
```

---

# ⚙️ Installation Guide

## 1️⃣ Clone Repository

```bash
git clone https://github.com/your-username/student-flask-blockchain.git
cd student-flask-blockchain
```

---

## 2️⃣ Create Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / MacOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3️⃣ Install Requirements

```bash
pip install -r requirements.txt
```

---

# ⛓️ Blockchain Setup

## Start Ganache

Open Ganache and copy:

* RPC URL
* Private Key
* Contract Address

---

## Deploy Smart Contract

```bash
truffle migrate --reset
```

---

## Configure Environment

Create `.env`

```env
SECRET_KEY=your_secret_key

GANACHE_URL=http://127.0.0.1:7545

CONTRACT_ADDRESS=your_contract_address

PRIVATE_KEY=your_private_key
```

---

# ▶️ Run Application

```bash
python app.py
```

Open browser:

```text
http://127.0.0.1:5000
```

---

# 📸 Application Modules

## 👨‍🎓 Student Management

* Add student
* Delete student
* View student list

## 🔍 Verification System

* Blockchain verification
* QR verification
* Hash comparison

## 📊 Dashboard

* Statistics
* Latest block info
* Transaction logs

## 📄 Export System

* Export PDF reports
* Generate QR Codes

---

# 🧪 Testing

Run blockchain test:

```bash
python test_blockchain.py
```

Run transaction test:

```bash
python test_tx_add_student.py
```

---

# 🎯 Future Improvements

* Face Recognition Integration
* NFT Student Identity
* IPFS Decentralized Storage
* Multi-University Support
* Mobile Application
* Role-Based Access Control

---

# 👨‍💻 Developer

**Nguyễn Mạnh Đức**

Blockchain Student Identity Verification System
Flask + Ethereum + Solidity + Web3.py

---

# 📄 License

This project is developed for educational and research purposes.

MIT License
