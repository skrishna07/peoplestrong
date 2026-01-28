# PeopleStrong ↔ ERP Integration

This project automates the **data synchronization** between PeopleStrong and ERP, including **pushing candidate data**, **pulling candidate documents**, **SFTP file handling**, and **email notifications**.

---

## Table of Contents

- [Overview](#overview)  
- [Requirements](#requirements)  
- [Environment Setup](#environment-setup)  
- [Workflow](#workflow)  
- [Function Descriptions](#function-descriptions)  
- [Usage](#usage)  
- [Logging](#logging)  
- [Contact](#contact)  

---

## Overview

The integration performs two main operations:

1. **Push**: Send candidate data from PeopleStrong to ERP via API.
2. **Pull**: Retrieve candidate documents from ERP and save them to PeopleStrong SFTP directories.  

All actions are logged and summarized in emails for auditing and tracking.

---

## Requirements

Install the required Python packages:

```bash
pip install -r requirements.txt
