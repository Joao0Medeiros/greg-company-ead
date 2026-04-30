# Backend GREG Company EAD

## Instalação

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Banco

O projeto espera o MySQL em:

```txt
mysql+pymysql://root:root123@localhost:3306/greg_company_ead
```

O seed inicial roda ao iniciar o backend e cria usuários/cursos demonstrativos.
