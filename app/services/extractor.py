from app.utils.text_cleaner import clean_text

SKILL_KEYWORDS = {
    "python",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "sqlite",
    "pandas",
    "numpy",
    "scikit-learn",
    "machine learning",
    "deep learning",
    "nlp",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "git",
    "github",
    "javascript",
    "typescript",
    "react",
    "node.js",
    "linux",
    "rest api",
    "graphql",
    "data analysis",
    "tensorflow",
    "pytorch",
    "llm",
    "rag",
}


def extract_skills(text: str) -> list[str]:
    cleaned = clean_text(text)
    found = []

    for skill in SKILL_KEYWORDS:
        if skill in cleaned:
            found.append(skill)

    return sorted(set(found))
