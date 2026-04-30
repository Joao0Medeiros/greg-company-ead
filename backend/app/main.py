from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os, shutil, csv, io, zipfile, json, re
from sqlalchemy import text
from database import engine

SECRET_KEY = "greg-company-dev-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

app = FastAPI(title="GREG Company EAD API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

class LoginPayload(BaseModel): email: str; password: str
class StudentCreatePayload(BaseModel):
    name: str; email: str; password: str = "123456"; course: str = "Programação Básica"; access_enabled: bool = True
class StudentAccessPayload(BaseModel): access_enabled: bool
class StudentUpdatePayload(BaseModel):
    name: str; email: str; password: Optional[str] = ""; access_enabled: bool = True; course_ids: List[int] = []
class CoursePayload(BaseModel):
    title: str; description: Optional[str] = ""; cover_url: Optional[str] = ""
class ModulePayload(BaseModel):
    course_id: int; title: str; description: Optional[str] = ""; module_order: int = 1; min_grade: float = 6; video_url: Optional[str] = ""; slide_url: Optional[str] = ""; available_at: Optional[str] = ""
class QuestionPayload(BaseModel):
    module_id: int; question: str; option_a: str; option_b: str; option_c: str; option_d: str; correct_option: str = "A"
class ReviewPayload(BaseModel): rating: int; comment: Optional[str] = ""
class QuizSubmitPayload(BaseModel): answers: Dict[str, str]

def nowstr(): return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
def next_id(items): return max([int(x["id"]) for x in items], default=0)+1
def safe_name(name): return re.sub(r"[^a-zA-Z0-9_.-]+","_",name)

users=[
 {"id":1,"name":"Admin GREG","email":"admin@gregcompany.com","password":"123456","role":"admin","access_enabled":True},
 {"id":2,"name":"Aluno Demonstração","email":"aluno@gregcompany.com","password":"123456","role":"student","access_enabled":True},
 {"id":3,"name":"Aluno Bloqueado","email":"bloqueado@gregcompany.com","password":"123456","role":"student","access_enabled":False},
]
courses=[
 {"id":1,"title":"Programação Básica","description":"Curso completo com lógica, variáveis, funções, web e prova final.","cover_url":"/uploads/demo_programacao.jpg","is_active":True},
 {"id":2,"title":"Excel Profissional","description":"Do básico ao avançado com fórmulas, gráficos e dashboards.","cover_url":"/uploads/demo_excel.jpg","is_active":True},
 {"id":3,"title":"Atendimento ao Cliente","description":"Comunicação, postura, excelência e resolução de problemas.","cover_url":"/uploads/demo_atendimento.jpg","is_active":True},
]
modules=[]
questions=[]
classes=[
 {"id":1,"name":"Turma Demonstração","description":"Turma inicial para apresentação","course_id":1},
 {"id":2,"name":"Turma Excel 2026","description":"Treinamento corporativo","course_id":2},
]
class_students={1:[2],2:[2]}
enrollments={2:[1,2,3],3:[1]}
grades=[]
responses=[]
reviews=[]
video_progress={}

def seed_modules():
    global modules, questions
    if modules: return
    mid=1; qid=1
    # Programação 12 etapas, quizzes nas 4,8,12 (12 é prova final obrigatória)
    prog_titles=["Boas-vindas e ambiente","Lógica de programação","Variáveis e tipos","Quiz: fundamentos","Condicionais","Laços de repetição","Funções","Quiz: prática de lógica","HTML básico","CSS básico","JavaScript básico","Prova final de programação"]
    for i,t in enumerate(prog_titles,1):
        modules.append({"id":mid,"course_id":1,"title":f"Etapa {i:02d} — {t}","description":t,"module_order":i,"min_grade":6,"video_url":"https://www.w3schools.com/html/mov_bbb.mp4","slide_url":"/uploads/demo_material.pdf","available_at":"","done":False,"locked":i>1,"grade":None,"video_progress":0})
        if i in [4,8,12]:
            for n in range(1,6):
                questions.append({"id":qid,"module_id":mid,"question":f"Pergunta {n} da etapa {i}: qual alternativa está correta?","option_a":"Alternativa A","option_b":"Alternativa B correta","option_c":"Alternativa C","option_d":"Alternativa D","correct_option":"B"})
                qid+=1
        mid+=1
    excel=["Introdução ao Excel","Células e formatação","Fórmulas básicas","Quiz: fórmulas","Funções úteis","Gráficos","Tabelas dinâmicas","Prova final de Excel"]
    for i,t in enumerate(excel,1):
        modules.append({"id":mid,"course_id":2,"title":f"Etapa {i:02d} — {t}","description":t,"module_order":i,"min_grade":6,"video_url":"https://www.w3schools.com/html/mov_bbb.mp4","slide_url":"/uploads/demo_material.pdf","available_at":"","done":False,"locked":i>1,"grade":None,"video_progress":0})
        if i in [4,8]:
            for n in range(1,6):
                questions.append({"id":qid,"module_id":mid,"question":f"Excel pergunta {n}: qual resposta correta?","option_a":"Soma","option_b":"Filtro","option_c":"Resposta correta","option_d":"Mesclar","correct_option":"C"})
                qid+=1
        mid+=1
    atend=["Postura profissional","Comunicação clara","Escuta ativa","Quiz: atendimento","Resolução de conflitos","Prova final de atendimento"]
    for i,t in enumerate(atend,1):
        modules.append({"id":mid,"course_id":3,"title":f"Etapa {i:02d} — {t}","description":t,"module_order":i,"min_grade":6,"video_url":"https://www.w3schools.com/html/mov_bbb.mp4","slide_url":"/uploads/demo_material.pdf","available_at":"","done":False,"locked":i>1,"grade":None,"video_progress":0})
        if i in [4,6]:
            for n in range(1,6):
                questions.append({"id":qid,"module_id":mid,"question":f"Atendimento pergunta {n}: escolha a melhor conduta.","option_a":"Ignorar","option_b":"Responder sem ouvir","option_c":"Escutar e orientar corretamente","option_d":"Encerrar conversa","correct_option":"C"})
                qid+=1
        mid+=1

def init_state_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY,
                data JSONB NOT NULL
            )
        """))


def export_state():
    return {
        "users": users,
        "courses": courses,
        "modules": modules,
        "questions": questions,
        "classes": classes,
        "class_students": class_students,
        "enrollments": enrollments,
        "grades": grades,
        "responses": responses,
        "reviews": reviews,
        "video_progress": {f"{k[0]}:{k[1]}": v for k, v in video_progress.items()},
    }


def import_state(data):
    global users, courses, modules, questions, classes
    global class_students, enrollments, grades, responses, reviews, video_progress

    if isinstance(data, str):
        data = json.loads(data)

    users = data.get("users", users)
    courses = data.get("courses", courses)
    modules = data.get("modules", modules)
    questions = data.get("questions", questions)
    classes = data.get("classes", classes)
    class_students = {int(k): v for k, v in data.get("class_students", class_students).items()}
    enrollments = {int(k): v for k, v in data.get("enrollments", enrollments).items()}
    grades = data.get("grades", grades)
    responses = data.get("responses", responses)
    reviews = data.get("reviews", reviews)

    raw_progress = data.get("video_progress", {})
    video_progress = {}
    for key, value in raw_progress.items():
        user_id, module_id = key.split(":")
        video_progress[(int(user_id), int(module_id))] = value


def save_state():
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app_state (id, data)
                VALUES (1, CAST(:data AS JSONB))
                ON CONFLICT (id)
                DO UPDATE SET data = CAST(:data AS JSONB)
            """),
            {"data": json.dumps(export_state(), ensure_ascii=False)}
        )


def load_state():
    init_state_table()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT data FROM app_state WHERE id = 1")).fetchone()

    if row:
        import_state(row[0])
    else:
        seed_modules()
        save_state()


load_state()

@app.middleware("http")
async def auto_save_state(request, call_next):
    response = await call_next(request)

    if request.url.path.startswith("/api") and request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        try:
            save_state()
        except Exception as e:
            print("Erro ao salvar estado no banco:", e)

    return response

def ensure_demo_files():
    for fname, content in [
        ("demo_material.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"),
        ("demo_programacao.jpg", b""),
        ("demo_excel.jpg", b""),
        ("demo_atendimento.jpg", b"")
    ]:
        p=os.path.join(UPLOAD_DIR,fname)
        if not os.path.exists(p):
            open(p,"wb").write(content)
ensure_demo_files()

def make_token(user):
    data={"sub":user["email"],"role":user["role"],"name":user["name"],"exp":datetime.utcnow()+timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email=payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    u=next((x for x in users if x["email"]==email),None)
    if not u: raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return u

def admin(user):
    if user["role"]!="admin": raise HTTPException(status_code=403, detail="Acesso apenas para admin")

def student_access(user):
    if user["role"]=="student" and not user.get("access_enabled",True):
        raise HTTPException(status_code=403, detail="Acesso bloqueado. Mensalidade pendente ou acesso desativado pelo administrador.")

def course_progress(user_id, course_id):
    ms=sorted([m for m in modules if m["course_id"]==course_id], key=lambda x:x["module_order"])
    if not ms: return 0, False
    done=sum(1 for m in ms if any(g["user_id"]==user_id and g["module_id"]==m["id"] and g["approved"] for g in grades) or m["module_order"]==1 and False)
    # Last module is mandatory final if has questions; completed only if approved.
    pct=round((done/len(ms))*100)
    return pct, done==len(ms)

def module_view(user, m):
    qs=[q for q in questions if q["module_id"]==m["id"]]
    g=next((g for g in grades if g["user_id"]==user["id"] and g["module_id"]==m["id"]),None)
    date_locked=False
    if m.get("available_at"):
        try: date_locked=datetime.fromisoformat(m["available_at"].replace("Z",""))>datetime.now()
        except Exception: date_locked=False
    locked=m.get("locked",False) or date_locked
    if user["role"]=="admin": locked=False
    return {**m,"has_quiz":len(qs)>0,"grade":g["grade"] if g else None,"done":bool(g and g["approved"]),"locked":locked,"date_locked":date_locked,"video_progress":video_progress.get((user["id"],m["id"]),0)}

@app.get("/api/health")
def health(): return {"status":"online"}

@app.post("/api/login")
def login(payload: LoginPayload):
    u=next((x for x in users if x["email"].lower()==payload.email.lower() and x["password"]==payload.password),None)
    if not u: raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    return {"access_token":make_token(u),"token_type":"bearer","user":{k:u[k] for k in ["id","name","email","role","access_enabled"]}}

@app.get("/api/me")
def me(user=Depends(get_current_user)): return {k:user[k] for k in ["id","name","email","role","access_enabled"]}

@app.get("/api/student/status")
def status(user=Depends(get_current_user)):
    if user["role"]!="student": return {"access_enabled":True,"payment_status":"Admin"}
    return {"access_enabled":user.get("access_enabled",True),"payment_status":"Em dia" if user.get("access_enabled",True) else "Mensalidade pendente"}

@app.get("/api/dashboard")
def dashboard(user=Depends(get_current_user)):
    admin(user)
    ranking=[]
    for u in users:
        if u["role"]=="student":
            gs=[g for g in grades if g["user_id"]==u["id"]]
            avg=round(sum(g["grade"] for g in gs)/len(gs),1) if gs else 0
            ranking.append({"id":u["id"],"name":u["name"],"email":u["email"],"average":avg,"approved_modules":sum(1 for g in gs if g["approved"])})
    perf=[]
    for c in courses:
        st=[u for u in users if u["role"]=="student" and c["id"] in enrollments.get(u["id"],[])]
        avgs=[]
        for u in st:
            gs=[g for g in grades if g["user_id"]==u["id"] and any(m["id"]==g["module_id"] and m["course_id"]==c["id"] for m in modules)]
            if gs: avgs.append(sum(g["grade"] for g in gs)/len(gs))
        perf.append({"title":c["title"],"students":len(st),"average":round(sum(avgs)/len(avgs),1) if avgs else 0,"approval_rate":round((sum(1 for u in st if course_progress(u["id"],c["id"])[1])/len(st))*100) if st else 0})
    return {"total_students":len([u for u in users if u["role"]=="student"]),"active_courses":len(courses),"average":round(sum(x["average"] for x in ranking)/len(ranking),1) if ranking else 0,"completion":round(sum(p["approval_rate"] for p in perf)/len(perf)) if perf else 0,"blocked_students":len([u for u in users if u["role"]=="student" and not u.get("access_enabled",True)]),"ranking":ranking,"course_performance":perf}

@app.get("/api/students")
def list_students(user=Depends(get_current_user)):
    admin(user)
    out=[]
    for u in users:
        if u["role"]=="student":
            cs=[c["title"] for c in courses if c["id"] in enrollments.get(u["id"],[])]
            gs=[g for g in grades if g["user_id"]==u["id"]]
            avg=round(sum(g["grade"] for g in gs)/len(gs),1) if gs else 0
            class_name=next((cl["name"] for cl in classes if u["id"] in class_students.get(cl["id"],[])), "Sem turma")
            out.append({"id":u["id"],"name":u["name"],"email":u["email"],"course":", ".join(cs) or "Sem curso","average":avg,"progress":0,"status":"Ativo" if u.get("access_enabled",True) else "Bloqueado","access_enabled":u.get("access_enabled",True),"payment_status":"Em dia" if u.get("access_enabled",True) else "Mensalidade pendente","class_name":class_name})
    return out

@app.post("/api/students")
def create_student(payload: StudentCreatePayload, user=Depends(get_current_user)):
    admin(user)
    if any(u["email"].lower()==payload.email.lower() for u in users): raise HTTPException(status_code=400, detail="Já existe aluno com este email")
    uid=next_id(users)
    users.append({"id":uid,"name":payload.name,"email":payload.email,"password":payload.password,"role":"student","access_enabled":payload.access_enabled})
    c=next((c for c in courses if c["title"]==payload.course), courses[0] if courses else None)
    enrollments[uid]=[c["id"]] if c else []
    return {"id":uid,"name":payload.name,"email":payload.email}

@app.get("/api/students/{student_id}")
def get_student(student_id:int,user=Depends(get_current_user)):
    admin(user)
    u=next((u for u in users if u["id"]==student_id and u["role"]=="student"),None)
    if not u: raise HTTPException(status_code=404, detail="Aluno não encontrado")
    return {"id":u["id"],"name":u["name"],"email":u["email"],"access_enabled":u.get("access_enabled",True),"course_ids":enrollments.get(u["id"],[])}

@app.put("/api/students/{student_id}")
def update_student(student_id:int,payload:StudentUpdatePayload,user=Depends(get_current_user)):
    admin(user)
    u=next((u for u in users if u["id"]==student_id and u["role"]=="student"),None)
    if not u: raise HTTPException(status_code=404, detail="Aluno não encontrado")
    u.update({"name":payload.name,"email":payload.email,"access_enabled":payload.access_enabled})
    if payload.password: u["password"]=payload.password
    enrollments[student_id]=payload.course_ids
    return {"ok":True}

@app.delete("/api/students/{student_id}")
def delete_student(student_id:int,user=Depends(get_current_user)):
    admin(user)
    global users, grades, responses, reviews
    users=[u for u in users if u["id"]!=student_id]
    enrollments.pop(student_id,None)
    grades=[g for g in grades if g["user_id"]!=student_id]
    responses=[r for r in responses if r["user_id"]!=student_id]
    reviews=[r for r in reviews if r["user_id"]!=student_id]
    for k in list(class_students.keys()):
        class_students[k]=[x for x in class_students[k] if x!=student_id]
    return {"ok":True}

@app.patch("/api/students/{student_id}/access")
def access(student_id:int,payload:StudentAccessPayload,user=Depends(get_current_user)):
    admin(user)
    u=next((u for u in users if u["id"]==student_id),None)
    if not u: raise HTTPException(status_code=404, detail="Aluno não encontrado")
    u["access_enabled"]=payload.access_enabled
    return {"ok":True}

@app.get("/api/courses")
def list_courses(user=Depends(get_current_user)):
    student_access(user)
    selected=courses if user["role"]=="admin" else [c for c in courses if c["id"] in enrollments.get(user["id"],[])]
    out=[]
    for c in selected:
        pct,comp=course_progress(user["id"],c["id"]) if user["role"]=="student" else (0,False)
        out.append({**c,"progress":pct,"completed":comp,"students":len([uid for uid,cs in enrollments.items() if c["id"] in cs])})
    return out

@app.post("/api/courses")
def create_course(payload:CoursePayload,user=Depends(get_current_user)):
    admin(user)
    cid=next_id(courses); c={"id":cid,"title":payload.title,"description":payload.description or "","cover_url":payload.cover_url or "","is_active":True}; courses.append(c); return c

@app.put("/api/courses/{course_id}")
def update_course(course_id:int,payload:CoursePayload,user=Depends(get_current_user)):
    admin(user)
    c=next((c for c in courses if c["id"]==course_id),None)
    if not c: raise HTTPException(status_code=404, detail="Curso não encontrado")
    c.update(payload.dict())
    return c

@app.delete("/api/courses/{course_id}")
def delete_course(course_id:int,user=Depends(get_current_user)):
    admin(user)
    global courses, modules, questions, grades, responses
    mids=[m["id"] for m in modules if m["course_id"]==course_id]
    courses=[c for c in courses if c["id"]!=course_id]
    modules=[m for m in modules if m["course_id"]!=course_id]
    questions=[q for q in questions if q["module_id"] not in mids]
    grades=[g for g in grades if g["module_id"] not in mids]
    responses=[r for r in responses if r["module_id"] not in mids]
    for uid in list(enrollments.keys()):
        enrollments[uid]=[cid for cid in enrollments[uid] if cid!=course_id]
    return {"ok":True}

@app.get("/api/courses/{course_id}/modules")
def list_modules(course_id:int,user=Depends(get_current_user)):
    student_access(user)
    return [module_view(user,m) for m in sorted([m for m in modules if m["course_id"]==course_id], key=lambda x:x["module_order"])]

@app.post("/api/modules")
def create_module(payload:ModulePayload,user=Depends(get_current_user)):
    admin(user)
    m={**payload.dict(),"id":next_id(modules),"locked":payload.module_order>1,"done":False,"grade":None,"video_progress":0}
    modules.append(m); return m

@app.put("/api/modules/{module_id}")
def update_module(module_id:int,payload:ModulePayload,user=Depends(get_current_user)):
    admin(user)
    m=next((m for m in modules if m["id"]==module_id),None)
    if not m: raise HTTPException(status_code=404, detail="Etapa não encontrada")
    m.update(payload.dict())
    return m

@app.delete("/api/modules/{module_id}")
def delete_module(module_id:int,user=Depends(get_current_user)):
    admin(user)
    global modules, questions, grades, responses
    modules=[m for m in modules if m["id"]!=module_id]
    questions=[q for q in questions if q["module_id"]!=module_id]
    grades=[g for g in grades if g["module_id"]!=module_id]
    responses=[r for r in responses if r["module_id"]!=module_id]
    return {"ok":True}

@app.post("/api/modules/{module_id}/complete")
def complete_module(module_id:int,user=Depends(get_current_user)):
    student_access(user)
    m=next((m for m in modules if m["id"]==module_id),None)
    if not m: raise HTTPException(status_code=404, detail="Etapa não encontrada")
    if any(q["module_id"]==module_id for q in questions): raise HTTPException(status_code=400, detail="Esta etapa possui quiz obrigatório.")
    grades[:] = [g for g in grades if not (g["user_id"]==user["id"] and g["module_id"]==module_id)]
    grades.append({"user_id":user["id"],"module_id":module_id,"grade":10,"approved":True,"created_at":nowstr()})
    # unlock next
    nextm=next((x for x in sorted([x for x in modules if x["course_id"]==m["course_id"]],key=lambda x:x["module_order"]) if x["module_order"]==m["module_order"]+1),None)
    if nextm: nextm["locked"]=False
    return {"approved":True,"message":"Próxima etapa liberada"}

@app.post("/api/modules/{module_id}/video-progress")
def vid(module_id:int,payload:Dict[str,Any],user=Depends(get_current_user)):
    video_progress[(user["id"],module_id)]=float(payload.get("progress",0)); return {"ok":True}

@app.get("/api/modules/{module_id}/activities")
def activities(module_id:int,user=Depends(get_current_user)):
    student_access(user)
    return [q for q in questions if q["module_id"]==module_id]

@app.post("/api/modules/{module_id}/submit-quiz")
def submit_quiz(module_id:int,payload:QuizSubmitPayload,user=Depends(get_current_user)):
    student_access(user)
    qs=[q for q in questions if q["module_id"]==module_id]
    if not qs: raise HTTPException(status_code=404, detail="Nenhum quiz encontrado")
    # fix: unanswered quiz cannot score 10
    if not payload.answers or any(str(q["id"]) not in payload.answers or not payload.answers.get(str(q["id"])) for q in qs):
        raise HTTPException(status_code=400, detail="Responda todas as perguntas antes de enviar.")
    correct=0
    for q in qs:
        ans=payload.answers.get(str(q["id"]))
        is_ok=ans==q["correct_option"]
        if is_ok: correct+=1
        responses.append({"user_id":user["id"],"student_name":user["name"],"email":user["email"],"module_id":module_id,"question_id":q["id"],"question":q["question"],"selected":ans,"correct":q["correct_option"],"is_correct":is_ok,"created_at":nowstr()})
    grade=round((correct/len(qs))*10,1)
    m=next(m for m in modules if m["id"]==module_id)
    approved=grade>=float(m.get("min_grade",6))
    grades[:] = [g for g in grades if not (g["user_id"]==user["id"] and g["module_id"]==module_id)]
    grades.append({"user_id":user["id"],"module_id":module_id,"grade":grade,"approved":approved,"created_at":nowstr()})
    if approved:
        nextm=next((x for x in sorted([x for x in modules if x["course_id"]==m["course_id"]],key=lambda x:x["module_order"]) if x["module_order"]==m["module_order"]+1),None)
        if nextm: nextm["locked"]=False
    return {"approved":approved,"grade":grade,"message":"Próxima etapa liberada" if approved else "Nota abaixo de 6. Responda novamente."}

@app.post("/api/questions")
def create_question(payload:QuestionPayload,user=Depends(get_current_user)):
    admin(user)
    q={**payload.dict(),"id":next_id(questions)}
    questions.append(q); return q

@app.delete("/api/questions/{question_id}")
def delete_question(question_id:int,user=Depends(get_current_user)):
    admin(user)
    global questions
    questions=[q for q in questions if q["id"]!=question_id]
    return {"ok":True}


@app.get("/api/final-exams/{course_id}")
def get_final_exam(course_id:int,user=Depends(get_current_user)):
    admin(user)
    ms=sorted([m for m in modules if m["course_id"]==course_id], key=lambda x:x["module_order"])
    final=next((m for m in ms if "prova final" in m["title"].lower()), ms[-1] if ms else None)
    if not final:
        return {"module_id":None,"title":"","question_count":0}
    qs=[q for q in questions if q["module_id"]==final["id"]]
    return {"module_id":final["id"],"title":final["title"],"question_count":len(qs),"min_grade":final.get("min_grade",6)}

@app.post("/api/final-exams/{course_id}/ensure")
def ensure_final_exam(course_id:int,user=Depends(get_current_user)):
    admin(user)
    c=next((c for c in courses if c["id"]==course_id),None)
    if not c:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    ms=sorted([m for m in modules if m["course_id"]==course_id], key=lambda x:x["module_order"])
    final=next((m for m in ms if "prova final" in m["title"].lower()), None)
    if not final:
        order=(max([m["module_order"] for m in ms], default=0)+1)
        final={"id":next_id(modules),"course_id":course_id,"title":f"Prova final — {c['title']}","description":"Avaliação final obrigatória do curso","module_order":order,"min_grade":6,"video_url":"","slide_url":"","available_at":"","done":False,"locked":order>1,"grade":None,"video_progress":0}
        modules.append(final)
    qs=[q for q in questions if q["module_id"]==final["id"]]
    return {"module_id":final["id"],"title":final["title"],"question_count":len(qs),"min_grade":final.get("min_grade",6)}

@app.get("/api/final-exams/{course_id}/questions")
def final_exam_questions(course_id:int,user=Depends(get_current_user)):
    admin(user)
    ms=sorted([m for m in modules if m["course_id"]==course_id], key=lambda x:x["module_order"])
    final=next((m for m in ms if "prova final" in m["title"].lower()), ms[-1] if ms else None)
    if not final:
        return []
    return [q for q in questions if q["module_id"]==final["id"]]

@app.get("/api/admin/quiz-results")
def quiz_results(user=Depends(get_current_user)):
    admin(user)
    return responses

@app.delete("/api/admin/quiz-results")
def clear_results(user=Depends(get_current_user)):
    admin(user)
    responses.clear(); grades.clear(); return {"ok":True}

@app.post("/api/courses/{course_id}/review")
def review(course_id:int,payload:ReviewPayload,user=Depends(get_current_user)):
    student_access(user)
    reviews.append({"course_id":course_id,"course_title":next((c["title"] for c in courses if c["id"]==course_id),"Curso"),"student_name":user["name"],"email":user["email"],"rating":max(1,min(5,payload.rating)),"comment":payload.comment})
    return {"ok":True}

@app.get("/api/admin/course-reviews")
def course_reviews(user=Depends(get_current_user)):
    admin(user); return reviews

@app.get("/api/classes")
def list_classes(user=Depends(get_current_user)):
    admin(user)
    return [{**cl,"course_title":next((c["title"] for c in courses if c["id"]==cl.get("course_id")),""),"students_count":len(class_students.get(cl["id"],[]))} for cl in classes]

@app.post("/api/classes")
def create_class(payload:Dict[str,Any],user=Depends(get_current_user)):
    admin(user)
    cl={"id":next_id(classes),"name":payload.get("name","Nova turma"),"description":payload.get("description",""),"course_id":payload.get("course_id")}
    classes.append(cl); class_students[cl["id"]]=[]; return cl

@app.get("/api/classes/{class_id}/students")
def class_students_list(class_id:int,user=Depends(get_current_user)):
    admin(user)
    ids=class_students.get(class_id,[])
    return [{"id":u["id"],"name":u["name"],"email":u["email"]} for u in users if u["id"] in ids]

@app.post("/api/classes/{class_id}/students")
def add_class_student(class_id:int,payload:Dict[str,Any],user=Depends(get_current_user)):
    admin(user)
    uid=int(payload.get("user_id"))
    class_students.setdefault(class_id,[])
    if uid not in class_students[class_id]: class_students[class_id].append(uid)
    return {"ok":True}

@app.delete("/api/classes/{class_id}/students/{student_id}")
def remove_class_student(class_id:int,student_id:int,user=Depends(get_current_user)):
    admin(user)
    class_students[class_id]=[x for x in class_students.get(class_id,[]) if x!=student_id]
    return {"ok":True}

@app.get("/api/reports/students.csv")
def report(user=Depends(get_current_user)):
    admin(user)
    f=io.StringIO(); w=csv.writer(f)
    w.writerow(["Aluno","Email","Cursos","Status","Média"])
    for s in list_students(user):
        w.writerow([s["name"],s["email"],s["course"],s["status"],s["average"]])
    return Response(f.getvalue(), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=relatorio_alunos.csv"})

@app.post("/api/upload/course-cover")
@app.post("/api/upload/content")
def upload(file:UploadFile=File(...), user=Depends(get_current_user)):
    admin(user)
    name=f"{int(datetime.utcnow().timestamp())}_{safe_name(file.filename)}"
    path=os.path.join(UPLOAD_DIR,name)
    with open(path,"wb") as out: shutil.copyfileobj(file.file,out)
    return {"file_url":f"/uploads/{name}","filename":file.filename}

@app.post("/api/courses/import-zip")
def import_zip(file:UploadFile=File(...), user=Depends(get_current_user)):
    admin(user)
    # Demo implementation: creates a sample imported course
    cid=next_id(courses)
    title=os.path.splitext(file.filename)[0].replace("_"," ").title()
    courses.append({"id":cid,"title":title,"description":"Curso importado por ZIP","cover_url":"","is_active":True})
    for i in range(1,4):
        modules.append({"id":next_id(modules),"course_id":cid,"title":f"Etapa {i:02d} importada","description":"Criada automaticamente","module_order":i,"min_grade":6,"video_url":"","slide_url":"","available_at":"","done":False,"locked":i>1,"grade":None,"video_progress":0})
    return {"message":"Curso importado em modo demonstração","course_id":cid}
