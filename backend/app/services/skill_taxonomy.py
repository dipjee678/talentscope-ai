"""Canonical skill taxonomy, synonym normalization, degree hierarchy, and deterministic
256-dimensional semantic vector embeddings for consistent, explainable CV-to-job matching.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Dict, List, Set, Tuple

# Canonical skill dictionary: canonical_display_name -> (category, aliases)
SKILL_CATALOG: Dict[str, Tuple[str, List[str]]] = {
    # Programming Languages
    "Python": ("programming_language", ["python", "python3", "py"]),
    "JavaScript": ("programming_language", ["javascript", "js", "ecmascript", "es6"]),
    "TypeScript": ("programming_language", ["typescript", "ts"]),
    "Java": ("programming_language", ["java", "jdk", "jvm", "java 17", "java 21"]),
    "C++": ("programming_language", ["c++", "cpp", "c/c++"]),
    "C": ("programming_language", ["c programming", "ansi c"]),
    "C#": ("programming_language", ["c#", "csharp", ".net c#"]),
    "Go": ("programming_language", ["golang", "go language"]),
    "Rust": ("programming_language", ["rust", "rustlang"]),
    "SQL": ("programming_language", ["sql", "t-sql", "pl/sql"]),
    "R": ("programming_language", ["r programming", "rstudio"]),
    "Kotlin": ("programming_language", ["kotlin"]),
    "Swift": ("programming_language", ["swift"]),
    "PHP": ("programming_language", ["php", "php8"]),
    "Ruby": ("programming_language", ["ruby"]),
    "Scala": ("programming_language", ["scala"]),
    "Dart": ("programming_language", ["dart"]),
    "Bash": ("programming_language", ["bash", "shell scripting", "sh", "zsh"]),
    "MATLAB": ("programming_language", ["matlab"]),
    # Frontend & Mobile
    "React": ("technical", ["react", "reactjs", "react.js"]),
    "Next.js": ("technical", ["next.js", "nextjs"]),
    "Vue.js": ("technical", ["vue", "vuejs", "vue.js", "nuxt", "nuxt.js"]),
    "Angular": ("technical", ["angular", "angularjs"]),
    "Svelte": ("technical", ["svelte", "sveltekit"]),
    "HTML/CSS": ("technical", ["html", "html5", "css", "css3", "sass", "scss"]),
    "Tailwind CSS": ("technical", ["tailwind", "tailwindcss", "tailwind css"]),
    "React Native": ("technical", ["react native"]),
    "Flutter": ("technical", ["flutter"]),
    "Redux": ("technical", ["redux", "zustand"]),
    # Backend & APIs
    "Node.js": ("technical", ["node.js", "nodejs", "express", "express.js", "nestjs"]),
    "FastAPI": ("technical", ["fastapi", "fast api"]),
    "Django": ("technical", ["django", "django rest framework", "drf"]),
    "Flask": ("technical", ["flask"]),
    "Spring Boot": ("technical", ["spring boot", "spring framework", "spring"]),
    ".NET": ("technical", [".net", ".net core", "asp.net", "asp.net core"]),
    "Ruby on Rails": ("technical", ["ruby on rails", "rails"]),
    "Laravel": ("technical", ["laravel"]),
    "GraphQL": ("technical", ["graphql", "apollo"]),
    "REST APIs": ("technical", ["rest api", "rest apis", "restful", "openapi", "swagger"]),
    "gRPC": ("technical", ["grpc", "protobuf"]),
    "Microservices": ("technical", ["microservices", "microservice architecture", "distributed systems"]),
    "Celery": ("technical", ["celery"]),
    "Kafka": ("technical", ["kafka", "apache kafka", "rabbitmq"]),
    # Databases
    "PostgreSQL": ("technical", ["postgresql", "postgres", "pgvector"]),
    "MySQL": ("technical", ["mysql", "mariadb"]),
    "MongoDB": ("technical", ["mongodb", "mongoose", "nosql"]),
    "Redis": ("technical", ["redis"]),
    "Elasticsearch": ("technical", ["elasticsearch", "opensearch"]),
    "DynamoDB": ("technical", ["dynamodb"]),
    "Snowflake": ("technical", ["snowflake", "bigquery", "redshift"]),
    # AI / ML / Data Science
    "Machine Learning": ("technical", ["machine learning", "ml", "supervised learning", "scikit-learn", "sklearn", "xgboost"]),
    "Deep Learning": ("technical", ["deep learning", "neural networks", "cnn", "rnn", "transformers"]),
    "PyTorch": ("technical", ["pytorch", "torch"]),
    "TensorFlow": ("technical", ["tensorflow", "keras"]),
    "NLP": ("technical", ["nlp", "natural language processing", "spacy", "hugging face", "huggingface"]),
    "LLMs & GenAI": ("technical", ["llm", "llms", "generative ai", "genai", "langchain", "llamaindex", "rag", "openai api", "prompt engineering"]),
    "Computer Vision": ("technical", ["computer vision", "opencv", "yolo", "ocr"]),
    "Data Analysis": ("technical", ["data analysis", "pandas", "numpy", "scipy", "matplotlib", "seaborn"]),
    "Data Engineering": ("technical", ["data engineering", "etl", "apache spark", "pyspark", "airflow", "dbt"]),
    "Power BI / Tableau": ("technical", ["tableau", "power bi", "powerbi", "looker"]),
    # Cloud, DevOps & Security
    "AWS": ("technical", ["aws", "amazon web services", "ec2", "s3", "lambda", "ecs", "eks"]),
    "GCP": ("technical", ["gcp", "google cloud", "google cloud platform", "vertex ai"]),
    "Azure": ("technical", ["azure", "microsoft azure"]),
    "Docker": ("technical", ["docker", "docker-compose", "containers", "containerization"]),
    "Kubernetes": ("technical", ["kubernetes", "k8s", "helm"]),
    "Terraform": ("technical", ["terraform", "iac", "infrastructure as code", "ansible", "pulumi"]),
    "CI/CD": ("technical", ["ci/cd", "github actions", "gitlab ci", "jenkins", "circleci"]),
    "Linux": ("technical", ["linux", "ubuntu", "unix"]),
    "Git": ("technical", ["git", "github", "gitlab", "version control"]),
    "Cybersecurity": ("technical", ["cybersecurity", "information security", "owasp", "oauth", "oauth2", "jwt", "penetration testing", "iam"]),
    "Testing & QA": ("technical", ["unit testing", "pytest", "jest", "playwright", "cypress", "selenium", "tdd", "qa automation"]),
    "Agile / Scrum": ("technical", ["agile", "scrum", "kanban", "jira"]),
    "Figma / UI-UX": ("technical", ["figma", "ui/ux", "ux design", "product design", "wireframing"]),
    # Soft Skills
    "Communication": ("soft", ["communication", "written communication", "verbal communication", "public speaking", "presentation"]),
    "Leadership": ("soft", ["leadership", "team leadership", "mentoring", "coaching", "people management"]),
    "Problem Solving": ("soft", ["problem solving", "problem-solving", "analytical thinking", "critical thinking"]),
    "Collaboration": ("soft", ["collaboration", "teamwork", "cross-functional", "stakeholder management"]),
    "Project Management": ("soft", ["project management", "time management", "ownership", "adaptability"]),
}

# Build fast lookup structures
ALIAS_TO_CANONICAL: Dict[str, Tuple[str, str]] = {}
COMPILED_SKILL_PATTERNS: List[Tuple[str, str, re.Pattern[str]]] = []

for canonical, (cat, aliases) in SKILL_CATALOG.items():
    all_terms = {canonical.lower(), *[a.lower() for a in aliases]}
    for term in all_terms:
        ALIAS_TO_CANONICAL[term] = (canonical, cat)
        escaped = re.escape(term)
        # Handle C++, C#, .NET, Node.js where \b fails on punctuation boundaries
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_+#])", re.I)
        COMPILED_SKILL_PATTERNS.append((canonical, cat, pattern))


DEGREE_LEVELS: Dict[str, int] = {
    "high_school": 1,
    "associate": 2,
    "bachelor": 3,
    "master": 4,
    "phd": 5,
}

DEGREE_PATTERNS: List[Tuple[str, str, re.Pattern[str]]] = [
    ("phd", "Ph.D. / Doctorate", re.compile(r"\b(ph\.?d\.?|doctorate|doctor of philosophy)\b", re.I)),
    ("master", "Master's Degree", re.compile(r"\b(master(?:'?s)?|m\.sc\.?|msc|m\.s\.|m\.tech|mtech|m\.eng|meng|mba|m\.a\.)\b", re.I)),
    ("bachelor", "Bachelor's Degree", re.compile(r"\b(bachelor(?:'?s)?|b\.sc\.?|bsc|b\.s\.|b\.tech|btech|b\.eng|beng|b\.e\.|b\.a\.|undergraduate)\b", re.I)),
    ("associate", "Associate Degree / Diploma", re.compile(r"\b(associate(?:'?s)?\s+degree|diploma|hnd)\b", re.I)),
]

SPOKEN_LANGUAGES = [
    "English", "German", "French", "Spanish", "Mandarin", "Chinese", "Japanese",
    "Korean", "Arabic", "Hindi", "Bengali", "Portuguese", "Dutch", "Swedish",
    "Italian", "Polish", "Turkish", "Russian",
]

COUNTRY_ALIASES: Dict[str, List[str]] = {
    "United States": ["united states", "usa", "u.s.", "u.s.a.", "us", "america", "new york", "san francisco", "seattle", "austin", "boston", "chicago", "california", "texas"],
    "United Kingdom": ["united kingdom", "uk", "u.k.", "great britain", "england", "scotland", "london", "manchester", "edinburgh", "cambridge"],
    "Germany": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne"],
    "Canada": ["canada", "toronto", "vancouver", "montreal", "ottawa", "calgary", "waterloo"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "Netherlands": ["netherlands", "holland", "amsterdam", "rotterdam", "eindhoven", "utrecht"],
    "Sweden": ["sweden", "sverige", "stockholm", "gothenburg", "göteborg", "malmö", "malmo"],
    "France": ["france", "paris", "lyon", "toulouse"],
    "Switzerland": ["switzerland", "zurich", "zürich", "geneva", "lausanne", "basel"],
    "Ireland": ["ireland", "dublin", "cork", "galway"],
    "Singapore": ["singapore"],
    "India": ["india", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi", "gurgaon", "noida"],
    "Bangladesh": ["bangladesh", "dhaka", "chittagong"],
    "United Arab Emirates": ["united arab emirates", "uae", "dubai", "abu dhabi"],
    "Japan": ["japan", "tokyo", "osaka"],
    "Spain": ["spain", "madrid", "barcelona"],
    "Poland": ["poland", "warsaw", "krakow", "kraków", "wroclaw"],
    "Remote / Worldwide": ["worldwide", "anywhere", "global", "remote", "work from anywhere", "all countries"],
}


def normalize_skill(name: str) -> Tuple[str, str]:
    key = name.strip().lower()
    if key in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[key]
    return (name.strip(), "technical")


def extract_skills_from_text(text: str) -> Dict[str, List[str]]:
    """Return categorized canonical skills found in text without inventing unseen skills."""
    found_prog: Set[str] = set()
    found_tech: Set[str] = set()
    found_soft: Set[str] = set()

    if not text:
        return {"programming_languages": [], "technical_skills": [], "soft_skills": []}

    for canonical, cat, pattern in COMPILED_SKILL_PATTERNS:
        if pattern.search(text):
            if cat == "programming_language":
                found_prog.add(canonical)
            elif cat == "soft":
                found_soft.add(canonical)
            else:
                found_tech.add(canonical)

    return {
        "programming_languages": sorted(found_prog),
        "technical_skills": sorted(found_tech),
        "soft_skills": sorted(found_soft),
    }


def detect_highest_degree(text: str) -> Tuple[str | None, int]:
    if not text:
        return None, 0
    best_label = None
    best_rank = 0
    for key, label, pattern in DEGREE_PATTERNS:
        if pattern.search(text):
            rank = DEGREE_LEVELS[key]
            if rank > best_rank:
                best_rank = rank
                best_label = label
    return best_label, best_rank


def infer_country_from_location(location_text: str) -> str:
    if not location_text:
        return "Worldwide"
    low = location_text.lower()
    for country, aliases in COUNTRY_ALIASES.items():
        if country == "Remote / Worldwide":
            continue
        for alias in aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", low):
                return country
    if any(tok in low for tok in ("worldwide", "anywhere", "global", "remote")):
        return "Worldwide"
    if "europe" in low or "emea" in low or "eu" in low.split():
        return "Europe"
    return location_text.strip()[:80]


def location_matches_countries(job_country: str, job_location_raw: str, job_work_mode: str, target_countries: List[str]) -> bool:
    """Check whether a job listing is relevant to the user's selected target countries."""
    if not target_countries:
        return True
    targets_lower = [t.lower().strip() for t in target_countries]
    if any(t in ("worldwide", "remote / worldwide", "any", "global", "remote") for t in targets_lower):
        return True

    combined = f"{job_country} {job_location_raw}".lower()
    for target in target_countries:
        tl = target.lower().strip()
        if tl in combined:
            return True
        for canonical, aliases in COUNTRY_ALIASES.items():
            if canonical.lower() == tl or tl in aliases:
                if any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", combined) for a in aliases):
                    return True
                if canonical in ("Germany", "Netherlands", "Sweden", "France", "Spain", "Poland", "Ireland", "Switzerland") and (
                    "europe" in combined or "emea" in combined
                ):
                    return True

    # Worldwide remote roles without country restrictions are eligible globally
    if job_work_mode == "remote" and job_country in ("Worldwide", "Remote / Worldwide"):
        if not any(
            restrict in combined
            for restrict in ("us only", "usa only", "uk only", "canada only", "eu only")
        ):
            return True

    return False


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "will", "your",
    "you", "are", "our", "work", "working", "team", "role", "job", "about", "who",
    "what", "into", "their", "they", "has", "been", "more", "can", "all", "new",
    "years", "year", "experience", "looking", "join", "company", "apply", "position",
}


def compute_semantic_embedding(text: str, dim: int = 256) -> List[float]:
    """Compute a deterministic, unit-normalized 256-dim feature-hashed unigram+bigram embedding.

    Works offline with zero external API latency and stores cleanly in pgvector or JSON.
    """
    vec = [0.0] * dim
    if not text:
        return vec

    tokens = [
        tok for tok in re.findall(r"[a-z0-9+#.]{2,}", text.lower())
        if tok not in STOPWORDS
    ]
    if not tokens:
        return vec

    features: List[Tuple[str, float]] = [(tok, 1.0) for tok in tokens]
    # Add bigrams for phrase sensitivity (e.g. "machine learning", "computer science")
    for i in range(len(tokens) - 1):
        features.append((f"{tokens[i]}_{tokens[i + 1]}", 1.25))

    # Boost canonical skills recognized in text
    skills = extract_skills_from_text(text)
    for sk in skills["programming_languages"] + skills["technical_skills"]:
        features.append((f"skill::{sk.lower()}", 2.5))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def cosine_similarity(vec_a: List[float] | None, vec_b: List[float] | None) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))
