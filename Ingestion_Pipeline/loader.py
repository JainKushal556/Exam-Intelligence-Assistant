from langchain_community.document_loaders import TextLoader ,PyMuPDFLoader
from pathlib import Path

def text_loader(path : Path ):
    path = Path(path)
    doc = TextLoader(path,encoding="utf-8")
    res = doc.load()
    return res

def pdf_loader(path : Path):
    path = Path(path)
    doc = PyMuPDFLoader(path , mode="page")
    res = doc.load()
    # print("metadata: ", res[0].metadata)
    return res
