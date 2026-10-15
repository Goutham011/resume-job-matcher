from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.schemas import MatchRequest, MatchResponse
from app.services.matcher import match_resume_to_jd
from app.services.parser import extract_text_from_pdf_bytes

app = FastAPI(title="Resume Job Matcher")


@app.get("/")
def read_root():
    return {"message": "Resume Job Matcher API is running"}


@app.post("/match", response_model=MatchResponse)
def match_endpoint(payload: MatchRequest):
    return match_resume_to_jd(
        resume_text=payload.resume_text,
        jd_text=payload.job_description,
    )


@app.post("/match-upload", response_model=MatchResponse)
async def match_upload_endpoint(
    resume_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    if resume_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    file_bytes = await resume_file.read()
    resume_text = extract_text_from_pdf_bytes(file_bytes)

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")

    return match_resume_to_jd(
        resume_text=resume_text,
        jd_text=job_description,
    )
