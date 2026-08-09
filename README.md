# 🌱 Kultiva

> **AI-powered precision farming and direct agricultural trade platform**

Kultiva is a Django-based AgriTech platform designed to connect **farmers, buyers, agricultural-input sellers, and administrators** through a single digital ecosystem. It combines machine-learning crop recommendations, localized soil intelligence, weather-aware advisory, marketplace workflows, digital trade proposals, escrow-style transaction tracking, and role-based administration.

The project is being evolved from an academic full-stack application into a **professional, domain-oriented Django architecture** while preserving the existing business behavior and database compatibility.

---

## 📌 Project Vision

Traditional agricultural supply chains often separate farm intelligence from commerce. Kultiva brings these capabilities together:

```text
             FARMER
                │
        ┌───────┴────────┐
        │                │
   AI AGRONOMY       MARKETPLACE
        │                │
  ┌─────┼─────┐          │
  │     │     │          │
Soil Weather Crop     Produce
  │     │     │          │
  └─────┴─────┘          │
        │                │
        └───────┬────────┘
                │
        DIRECT AGRICULTURAL
              TRADE
                │
       ┌────────┴────────┐
       │                 │
     BUYER             SELLER
       │                 │
       └────────┬────────┘
                │
          ADMIN / TRUST
```

The long-term objective is to make agricultural decision-making **data-driven**, agricultural commerce **transparent**, and the relationship between producers and purchasers **direct and traceable**.

---

## ✨ Core Capabilities

### 👨‍🌾 Farmer

- Farmer registration and authentication
- Farmer profile and address management
- Geographic coordinate handling
- Soil report submission
- Grid-based soil intelligence
- Manual laboratory soil reports
- Weather intelligence
- AI crop prediction
- Crop/advisory information
- Produce marketplace listings
- Inventory management
- Input marketplace purchasing
- Order history and invoices
- Direct trade proposals
- QR-assisted trade workflow
- Transaction and review history

### 🏢 Buyer

- Buyer registration and verification
- Company/GST/IEC information
- Farmer discovery
- Produce discovery
- Direct trade proposals
- Negotiation workflows
- Escrow-style transaction tracking
- Pickup scheduling
- Purchase history
- Invoice information
- Refund workflows
- Reviews and trust signals

### 🛒 Seller

- Seller registration and verification
- Shop profile
- Agricultural input listings
- Stock management
- Product editing/removal
- Order management
- Order-status updates
- Seller reports
- Receipt/invoice workflows

### 🛡️ Administration

- Farmer management
- Buyer management
- Seller management
- Account approval/verification
- Marketplace moderation
- Product takedown
- Soil-report management
- B2B refund resolution
- B2C refund resolution
- Order ledgers
- Farmer analytics
- Buyer analytics
- Seller analytics
- Email communication

---

# 🤖 AI & Intelligence Layer

Kultiva's intelligence layer is intentionally separated from the web/application layer so that AI components can evolve independently.

## 🌾 Crop Prediction

The crop prediction pipeline evaluates agricultural inputs such as:

- Nitrogen (N)
- Phosphorus (P)
- Potassium (K)
- Soil pH
- Weather/environmental information

The existing implementation uses a machine-learning classification pipeline and exposes the prediction through a dedicated service boundary.

## 🧪 Soil Intelligence

Kultiva supports two soil-data paths:

1. **Geospatial grid data** for locations covered by the soil dataset.
2. **Manual/laboratory reports** for farmers outside the available grid or requiring verified laboratory values.

The application can combine verified manual values with the agricultural intelligence pipeline.

## 🌦️ Weather Intelligence

Weather processing combines:

- Farmer location
- Latitude/longitude
- District information
- Current/forecast information where available
- Historical fallback data

The weather service is designed to continue providing useful agricultural context even when an external weather source is unavailable.

## 🌱 Agricultural Advisory

The advisory layer provides crop-specific guidance that can be consumed by the farmer dashboard and recommendation workflow.

---

# 🏗️ Architecture

Kultiva is moving toward a domain-oriented architecture rather than keeping every model and view inside one Django application.

```text
Kultiva/
│
├── backend/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── farmers/
│   │   ├── buyers/
│   │   ├── sellers/
│   │   ├── marketplace/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── escrow/
│   │   ├── soil/
│   │   ├── weather/
│   │   ├── advisory/
│   │   ├── reviews/
│   │   ├── notifications/
│   │   ├── analytics/
│   │   └── admin_portal/
│   │
│   ├── ai/
│   │   ├── crop_prediction/
│   │   ├── soil_analysis/
│   │   ├── weather_intelligence/
│   │   └── recommendations/
│   │
│   ├── core/
│   │   └── legacy/
│   │
│   ├── requirements/
│   └── tests/
│
├── Kultiva/
│   ├── manage.py
│   ├── Kultiva/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   ├── templates/
│   ├── static/
│   ├── media/
│   └── data/
│
├── docs/
├── infrastructure/
├── scripts/
├── tests/
├── tools/
└── .github/workflows/
```

### Domain ownership

| Domain | Responsibility |
|---|---|
| `accounts` | Users, roles, addresses, authentication identity |
| `farmers` | Farmer profiles, farm workflows, farmer-specific actions |
| `buyers` | Buyer profiles, procurement workflows |
| `sellers` | Seller profiles and input-store workflows |
| `marketplace` | Listings, catalog and marketplace operations |
| `orders` | B2C input orders and order lifecycle |
| `payments` | Payment-related transaction concerns |
| `escrow` | Direct-trade escrow and QR/security workflow |
| `soil` | Soil grids and manual soil reports |
| `weather` | Weather history and weather intelligence integration |
| `advisory` | Crop-specific agricultural guidance |
| `reviews` | Transaction-backed trust and reviews |
| `notifications` | User-facing notification responsibilities |
| `analytics` | Business and administrative reporting |
| `admin_portal` | Administrative operations and moderation |

---

# 🗄️ Data Model

The major business entities are:

```text
User
 ├── Address
 ├── FarmerProfile
 ├── BuyerProfile
 ├── SellerProfile
 ├── MarketplaceListing
 ├── InputOrder
 ├── DirectTradeProposal
 ├── EscrowTransaction
 ├── ManualSoilReport
 └── UnifiedReview

MarketplaceListing
 ├── DirectTradeProposal
 ├── InputOrder
 └── EscrowTransaction

DirectTradeProposal
 └── UnifiedReview

InputOrder
 └── UnifiedReview

GridSoilData
WeatherHistory
PincodeDirectory
```

The current database contains existing production/academic data, so architectural extraction is being performed with **database compatibility as a hard requirement**. Model/table ownership must not be changed casually because doing so can create destructive migrations or orphan existing records.

---

# 🔐 Security & Trust

Kultiva includes several trust-oriented mechanisms:

- Django authentication
- Role-based access control
- User verification status
- Farmer/buyer/seller separation
- Transaction-backed reviews
- Aadhar/GST/license availability checks
- QR/security-token trade workflow
- Escrow transaction states
- Admin moderation
- Refund resolution workflows
- Password recovery flow

> Production deployment must replace development credentials, configure a real secret key, restrict `ALLOWED_HOSTS`, configure HTTPS, and use environment variables for all secrets.

---

# 💻 Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python / Django |
| Authentication | Django Authentication |
| Database | SQLite for current development setup |
| Machine Learning | scikit-learn |
| Data Processing | NumPy / pandas |
| Image Processing | Pillow |
| QR Generation | qrcode |
| Frontend | HTML / CSS / JavaScript |
| Email | Django email backend / SMTP |
| Testing | Python `unittest` + Django checks |
| CI | GitHub Actions |

The architecture is designed so that PostgreSQL and production infrastructure can be introduced without redesigning the business domains.

---

# 🚀 Local Development

## 1. Clone the repository

```bash
git clone https://github.com/akhilrajakraj/Kultiva.git
cd Kultiva
```

## 2. Create a virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/base.txt
```

## 4. Configure environment variables

Copy the environment template and provide local values.

```bash
cp .env.example .env
```

On Windows, copy the file manually if `cp` is unavailable.

Never commit real credentials, API keys, SMTP passwords, or production secrets.

## 5. Run Django checks

From the Django project directory:

```bash
cd Kultiva
python manage.py check
```

## 6. Apply migrations

```bash
python manage.py migrate
```

## 7. Start the development server

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

---

# 🧪 Testing

The repository uses automated checks to prevent architectural extraction from silently breaking the application.

Run syntax validation:

```bash
python -m compileall backend
```

Run Django checks:

```bash
cd Kultiva
python manage.py check
```

Run the backend boundary tests:

```bash
python -m unittest discover -s ../backend/tests -t .. -p 'test_*.py' -v
```

GitHub Actions runs the same validation pipeline on pushes and pull requests.

The architecture-migration branch has already been validated with:

- dependency installation
- Python compilation
- Django system checks
- domain-boundary tests

---

# 🔄 Architecture Migration Strategy

The repository is being migrated incrementally from a legacy monolithic Django application to domain-oriented applications.

### Phase 1 — Architecture foundation

- Establish domain directories
- Establish AI boundaries
- Add compatibility layer
- Add CI
- Add automated boundary tests

### Phase 2 — Model extraction

- Move model ownership into the appropriate domain applications
- Preserve database table names
- Preserve relationships and constraints
- Create safe migrations
- Verify existing data

### Phase 3 — Service extraction

Move business logic out of HTTP views:

```text
views.py
   ↓
services.py
   ↓
selectors.py
   ↓
models.py
```

### Phase 4 — View extraction

Move endpoint responsibilities into their owning domain apps while keeping URL names and user-visible behavior stable.

### Phase 5 — Test expansion

Add unit, integration, model, service, authentication, transaction, and HTTP workflow tests for each domain.

### Phase 6 — Legacy removal

Only after all routes, services, models, migrations, and tests have been verified will the compatibility layer and legacy monolith be removed.

**Important:** The legacy layer must not be deleted simply because the new directory exists. It is removed only after behavioral parity has been demonstrated by tests.

---

# 🧭 Engineering Principles

Kultiva follows these architectural rules during the migration:

1. **Do not duplicate business logic.**
2. **Do not create duplicate database tables accidentally.**
3. **Preserve existing data.**
4. **Keep domain ownership explicit.**
5. **Keep AI code independent from HTTP code.**
6. **Move business logic into services.**
7. **Use selectors for complex read/query logic.**
8. **Keep views thin.**
9. **Add tests before deleting compatibility code.**
10. **Every extraction must pass CI before the next extraction begins.**

---

# 📊 Current Development Status

| Area | Status |
|---|---|
| Professional directory architecture | 🟢 Established |
| Domain compatibility boundaries | 🟢 Established |
| AI service boundaries | 🟢 Established |
| CI pipeline | 🟢 Passing |
| Django system check | 🟢 Passing |
| Boundary tests | 🟢 Passing |
| Full model physical extraction | 🟡 In progress |
| Full service extraction | 🟡 In progress |
| Full view extraction | 🟡 In progress |
| Legacy monolith removal | 🔴 Not yet safe |
| Production deployment hardening | 🔴 Pending |

---

# 🧰 Useful Commands

```bash
# Django checks
python manage.py check

# Migrations
python manage.py makemigrations
python manage.py migrate

# Development server
python manage.py runserver

# Test suite
python -m unittest discover -s ../backend/tests -t .. -p 'test_*.py' -v

# Python syntax validation
python -m compileall ../backend
```

---

# 🤝 Contributing

When adding a feature:

1. Identify the domain that owns it.
2. Add or update the domain model if required.
3. Put business rules in `services.py`.
4. Put complex reads in `selectors.py`.
5. Keep the view responsible for HTTP concerns only.
6. Add tests.
7. Run Django checks.
8. Run the complete test suite.
9. Verify database migrations.
10. Open a pull request only after CI passes.

---

# 📚 Documentation

Recommended documentation areas:

```text
docs/
├── architecture/
├── api/
├── database/
├── ai/
├── deployment/
├── security/
└── decisions/
```

Architecture decisions should be recorded rather than relying on undocumented assumptions in the codebase.

---

# 🔮 Future Roadmap

Potential future capabilities include:

- Real-time weather integrations
- Satellite imagery analysis
- Drone-based crop monitoring
- Plant-disease detection
- IoT soil sensors
- Crop-price prediction
- Demand forecasting
- Mobile application
- Multilingual agricultural assistant
- PostgreSQL production deployment
- Background task processing
- Object storage for agricultural media
- Advanced marketplace recommendations
- Supply-chain traceability

---

# 🎓 Academic Context

Kultiva originated as a final-year Computer Science project demonstrating how Artificial Intelligence, Machine Learning, database systems, and full-stack web development can be applied to agricultural problems.

The architecture is being improved beyond a conventional academic monolith so that the project can serve as a stronger example of professional backend engineering, domain separation, testing, CI, and maintainable AI integration.

---

# 👨‍💻 Author

**Akhil Raj**

Bachelor of Computer Science

---

## 📄 License

Add the project's chosen open-source or academic license here before distributing Kultiva publicly.
