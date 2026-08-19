from fastapi import FastAPI

app = FastAPI(title='AGI Platform')

@app.get('/')
def root():
    return {'status':'ok'}
