import streamlit as st
import psycopg2


def conectar():

    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"]
    )


def criar_banco():

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id SERIAL PRIMARY KEY,
        materia TEXT,
        assunto TEXT,
        banca TEXT,
        cargo TEXT,
        ano INTEGER,
        dificuldade TEXT,
        tags TEXT,
        questao TEXT,
        gabarito TEXT,
        comentario TEXT,
        observacoes TEXT,
        status TEXT DEFAULT 'Não respondida'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estatisticas_tag (
        id SERIAL PRIMARY KEY,
        tag TEXT,
        ciclo INTEGER,
        acertos INTEGER DEFAULT 0,
        erros INTEGER DEFAULT 0
    )
    """)

    conn.commit()

    conn.close()