# AssetIQ – Intelligent Asset Management Chatbot

## Project Overview

AssetIQ is an AI-powered Intelligent Asset Management Chatbot designed to simplify IT asset management within an organization.

It allows users to interact with organizational asset data using natural language instead of manually searching through database tables. The chatbot provides information about IT assets, employees, departments, asset allocations, and maintenance records.

The system combines **Retrieval-Augmented Generation (RAG), a Knowledge Graph, Natural Language Processing (NLP), and a Large Language Model (LLM)** to deliver relevant and context-aware responses.

## Key Features

- **AI-Powered Chatbot:** Ask questions about organizational IT assets using natural language.
- **Asset Inventory Management:** Retrieve asset details, categories, brands, models, and availability.
- **Employee Asset Tracking:** Identify which assets are assigned to particular employees.
- **Department Information:** Access employee and department-related information.
- **Maintenance Tracking:** Retrieve maintenance records, reported issues, and maintenance status.
- **Retrieval-Augmented Generation (RAG):** Retrieve relevant information from the asset management knowledge base.
- **Knowledge Graph:** Represent relationships between employees, assets, departments, categories, and maintenance records.
- **Natural Language Queries:** Convert user questions into meaningful database operations.
- **Interactive Dashboard:** Access asset information through a user-friendly web interface.

## Technologies Used

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend Framework | Flask |
| Frontend | HTML, CSS, JavaScript, Bootstrap |
| Database | MySQL |
| AI Model | Google Gemini |
| AI Architecture | Retrieval-Augmented Generation (RAG) |
| Knowledge Representation | Knowledge Graph |
| NLP | Natural Language Processing |
| Database Connectivity | MySQL Connector |
| SQL Processing | SQLGlot |

## System Architecture

AssetIQ follows an integrated architecture:

1. **User Interface:** Users enter questions through the web-based chatbot.
2. **Flask Backend:** Handles requests and coordinates application components.
3. **Natural Language Processing:** Processes and interprets user queries.
4. **Database Retrieval:** Retrieves structured information from the MySQL database.
5. **RAG Component:** Retrieves relevant information from the asset management knowledge base.
6. **Knowledge Graph:** Represents relationships between organizational entities.
7. **LLM Integration:** Google Gemini helps generate meaningful natural-language responses.
8. **Response Generation:** Presents the retrieved information to the user.

## Database Modules

The project uses the following MySQL tables:

- `employees` – Stores employee information.
- `departments` – Stores department details.
- `assets` – Stores IT asset information.
- `asset_categories` – Stores asset categories.
- `allocations` – Maintains employee-to-asset allocation records.
- `maintenance` – Stores asset maintenance information.

## Example Questions

Users can ask questions such as:

- How many employees are registered in the database?
- Which laptops are currently available?
- Which laptop is assigned to a particular employee?
- What assets are assigned to an employee?
- Which assets are currently under maintenance?
- Show the maintenance history of an asset.
- Which department does a particular employee belong to?

## Project Structure

```text
AssetIQ/
│
├── app.py
├── chatbot/
├── database/
├── knowledge_base/
├── static/
├── templates/
├── requirements.txt
├── test_gemini.py
├── test_mysql_chatbot.py
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ShravaniChavan0306/AssetIQ.git
cd AssetIQ
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root and configure the required environment variables.

Add your Google Gemini API key and the database connection details required by the application.

**Important:** Never upload your `.env` file or expose API keys, passwords, or database credentials on GitHub.

### 5. Configure MySQL Database

- Install and start MySQL Server.
- Create the `assetiq_db` database.
- Configure the database connection.
- Import or execute the required database schema and data.

### 6. Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Project Objectives

- Simplify organizational IT asset management.
- Reduce manual database searching.
- Improve asset allocation transparency.
- Provide quick access to maintenance information.
- Enable natural-language interaction with structured organizational data.
- Demonstrate the practical integration of AI, RAG, Knowledge Graphs, and relational databases.

## Future Enhancements

- Role-based authentication and access control.
- Automated asset allocation recommendations.
- Advanced reporting and analytics.
- Improved knowledge graph visualization.
- Asset maintenance alerts and notifications.
- Integration with additional organizational management systems.

## Developer

**Project Name:** AssetIQ – Intelligent Asset Management Chatbot

**Project Developer:** Shravani

**Project Domain:** Artificial Intelligence, Database Management, and Intelligent Information Retrieval.

---

*AssetIQ – Making Intelligent Asset Management Simpler with AI.*
