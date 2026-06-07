import psycopg2
import streamlit as st


def get_conn():
    """Retorna uma conexão com o Supabase via secrets do Streamlit."""
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=10,
    )


def criar_banco():
    """Cria as tabelas no Supabase caso ainda não existam."""

    conn = get_conn()
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
        status TEXT DEFAULT 'Não respondida',
        dominio TEXT DEFAULT ''
    )
    """)

    # Garante a coluna dominio em bancos já existentes
    cursor.execute("""
        ALTER TABLE questoes ADD COLUMN IF NOT EXISTS dominio TEXT DEFAULT ''
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
    cursor.close()
    conn.close()
