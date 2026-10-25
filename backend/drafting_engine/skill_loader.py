from pathlib import Path
import yaml

SKILLS_DIR = Path(__file__).parent / "skills"


def load_skills():
    skills = {}
    for f in SKILLS_DIR.glob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        skills[data["id"]] = data
    return skills


def get_skill(skill_id):
    skills = load_skills()
    if skill_id not in skills:
        raise KeyError(f"Unknown skill: {skill_id}. Available: {list(skills)}")
    return skills[skill_id]