"""Entry point — run with: uvicorn main:app or python main.py"""

from digitaltwin.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
