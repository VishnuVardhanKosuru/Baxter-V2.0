# Jira FRD & Manual Test Cases Fetcher Agent 🤖

An intelligent AI Agent built in Python that connects to **Jira Cloud (Free/Standard/Enterprise)**, extracts issue metadata and attachments, uses an **LLM (Google Gemini or OpenAI)** to analyze and classify document types, and automatically downloads and names:
- **FRDs (Functional Requirement Documents)** -> Saved in `./output/frd/`
- **Manual Test Cases** -> Saved in `./output/testcases/`

---

## 📌 Features
- **Automatic Jira Cloud Integration**: Connects via Jira Cloud REST API v3 using Atlassian API Token authentication.
- **LLM Attachment Classifier**: Intelligent classification of attached documents (`.docx`, `.pdf`, `.xlsx`, `.csv`, `.txt`, `.md`) into FRD or Manual Test Cases using Gemini or OpenAI.
- **Standardized Naming Convention**: Replaces messy original filenames with clean, structured names based on Issue Key, Feature Name, and Document Type:
  - FRD: `{ISSUE_KEY}_{FeatureName}_FRD_{Version}.{ext}`
  - Manual Test Cases: `{ISSUE_KEY}_{FeatureName}_Manual_TestCases_{Version}.{ext}`
- **Fallback Rule-Based Classifier**: Functions smoothly even if LLM API keys are not provided.
- **Rich CLI Output**: Formatted tables and progress indicators in terminal.

---

## 🛠️ Step 1: Installation

1. Open your terminal in this directory:
   ```bash
   cd c:\Users\2878282\Downloads\jira-sreeja
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🔑 Step 2: How to Get Atlassian API Token & Configure `.env`

### 1. Generate Atlassian API Token
1. Go to Atlassian Account Security Settings: [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**.
3. Label it (e.g. `JiraAgentToken`), click **Create**, and copy the generated token string.

### 2. Configure `.env` File
Open the `.env` file in this directory and fill in your values:

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@domain.com
JIRA_API_TOKEN=your_atlassian_api_token_here

# LLM Configuration (Google Gemini API Key from Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here
LLM_PROVIDER=gemini

OUTPUT_DIR=./output
```

---

## 🚀 Step 3: Running the Jira Agent

### 1. Run Mock Dry-Run Mode (No credentials required)
Test the agent logic and LLM naming parser immediately with simulated Jira data:
```bash
python jira_agent.py --mock
```

### 2. Fetch FRDs and Test Cases for a Specific Jira Issue Key
```bash
python jira_agent.py --issue BANK-101
```

### 3. Fetch FRDs and Test Cases using a JQL Search Query
```bash
python jira_agent.py --jql "project = BANK AND attachment IS NOT EMPTY"
```

---

## 📂 Output Folder Structure
After execution, files will be downloaded and saved automatically:

```text
jira-sreeja/
├── output/
│   ├── frd/
│   │   ├── BANK-101_UserAuthentication_FRD_v1.0.docx
│   │   └── PAY-204_PaymentGateway_FRD.pdf
│   ├── testcases/
│   │   ├── BANK-101_UserAuthentication_Manual_TestCases_v1.0.xlsx
│   │   └── PAY-204_PaymentGateway_Manual_TestCases.csv
│   └── other/
│       └── architecture_diagram.png
```
