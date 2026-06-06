import streamlit as st
import sqlite3
import os
import shutil
import openpyxl
import plotly.graph_objects as go
from datetime import datetime
from database import criar_banco, conectar

criar_banco()

try:

    conn = conectar()

    conn.close()

    st.success("✅ Conectado ao Supabase")

except Exception as e:

    st.error(f"Erro Supabase: {e}")

# ===================================================
# BACKUP AUTOMÁTICO
# ===================================================

def fazer_backup():
    """Copia banco.db para /backups com timestamp. Mantém os 10 mais recentes."""

    os.makedirs("backups", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    destino = f"backups/banco_{timestamp}.db"

    if os.path.exists("banco.db"):
        shutil.copy2("banco.db", destino)

    # Manter só os 10 backups mais recentes
    arquivos = sorted(
        [f for f in os.listdir("backups") if f.endswith(".db")]
    )

    while len(arquivos) > 10:
        os.remove(os.path.join("backups", arquivos.pop(0)))


if "backup_feito" not in st.session_state:
    fazer_backup()
    st.session_state["backup_feito"] = True


# ===================================================
# CONFIGURAÇÃO
# ===================================================

st.set_page_config(
    page_title="Banco de Questões",
    layout="wide"
)

st.title("📚 Banco de Questões Para Seu Futuro Cargo")

menu_opcoes = [
    "Cadastrar Questão",
    "Importar por Excel",
    "Resolver Questões",
    "Revisar Questões",
    "Estatísticas",
    "Dashboard",
]

indice_menu = 0

if "menu_override" in st.session_state:
    try:
        indice_menu = menu_opcoes.index(
            st.session_state.pop("menu_override")
        )
    except ValueError:
        indice_menu = 0

menu = st.sidebar.selectbox(
    "Menu",
    menu_opcoes,
    index=indice_menu
)


# ===================================================
# FUNÇÕES AUXILIARES
# ===================================================

def atualizar_estatisticas_tag(cursor, tags, novo_status):
    """Atualiza acertos/erros por tag no ciclo atual."""

    for tag in tags.splitlines():

        tag = tag.strip()

        if not tag:
            continue

        cursor.execute("""
        SELECT ciclo
        FROM estatisticas_tag
        WHERE tag = ?
        ORDER BY ciclo DESC
        LIMIT 1
        """, (tag,))

        ciclo_atual = cursor.fetchone()

        if ciclo_atual:
            ciclo_atual = ciclo_atual[0]
        else:
            ciclo_atual = 1
            cursor.execute("""
            INSERT INTO estatisticas_tag (tag, ciclo, acertos, erros)
            VALUES (?, ?, 0, 0)
            """, (tag, ciclo_atual))

        if novo_status == "Acertada":
            cursor.execute("""
            UPDATE estatisticas_tag
            SET acertos = acertos + 1
            WHERE tag = ? AND ciclo = ?
            """, (tag, ciclo_atual))
        else:
            cursor.execute("""
            UPDATE estatisticas_tag
            SET erros = erros + 1
            WHERE tag = ? AND ciclo = ?
            """, (tag, ciclo_atual))


def get_todas_tags():
    """Retorna lista ordenada de todas as tags únicas do banco."""

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM questoes")
    registros = cursor.fetchall()
    conn.close()

    lista = []
    for registro in registros:
        if registro[0]:
            for tag in registro[0].splitlines():
                tag = tag.strip()
                if tag and tag not in lista:
                    lista.append(tag)

    lista.sort()
    return lista


# ===================================================
# CADASTRAR QUESTÃO
# ===================================================

if menu == "Cadastrar Questão":

    st.header("Nova Questão")

    materia = st.text_input("Matéria")

    assunto = st.text_input("Assunto")

    banca = st.text_input("Banca")

    cargo = st.text_input("Cargo")

    ano = st.number_input(
        "Ano",
        min_value=2000,
        max_value=2100,
        value=2025
    )

    dificuldade = st.selectbox(
        "Dificuldade",
        [
            "Muito Fácil",
            "Fácil",
            "Média",
            "Difícil",
            "Muito Difícil",
            "Pegadinha"
        ]
    )

    tags = st.text_area(
        "Tags (uma por linha)",
        height=120
    )

    questao = st.text_area("Questão")

    gabarito = st.selectbox(
        "Gabarito",
        [
            "Certo",
            "Errado"
        ]
    )

    comentario = st.text_area("Comentário")

    if st.button("Salvar"):

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO questoes
        (materia, assunto, banca, cargo, ano, dificuldade,
         tags, questao, gabarito, comentario, observacoes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            materia, assunto, banca, cargo, ano, dificuldade,
            tags, questao, gabarito, comentario, "", "Não respondida"
        ))

        conn.commit()
        conn.close()

        st.success("Questão salva com sucesso!")


# ===================================================
# IMPORTAR POR EXCEL
# ===================================================

elif menu == "Importar por Excel":

    st.header("📥 Importação em Lote por Excel")

    st.markdown("""
    **Formato esperado da planilha (uma questão por linha):**

    | materia | assunto | banca | cargo | ano | dificuldade | tags | questao | gabarito | comentario |
    |---------|---------|-------|-------|-----|-------------|------|---------|----------|------------|

    - **dificuldade**: Muito Fácil / Fácil / Média / Difícil / Muito Difícil / Pegadinha
    - **gabarito**: Certo / Errado
    - **tags**: separe múltiplas tags com ponto e vírgula (`;`)
    - A primeira linha deve ser o cabeçalho (será ignorada automaticamente)
    """)

    arquivo = st.file_uploader(
        "Selecione o arquivo Excel (.xlsx)",
        type=["xlsx"]
    )

    if arquivo:

        try:
            wb = openpyxl.load_workbook(arquivo)
            ws = wb.active

            cabecalho = [str(cell.value).strip().lower() if cell.value else "" for cell in ws[1]]

            colunas_esperadas = [
                "materia", "assunto", "banca", "cargo", "ano",
                "dificuldade", "tags", "questao", "gabarito", "comentario"
            ]

            faltando = [c for c in colunas_esperadas if c not in cabecalho]

            if faltando:
                st.error(f"Colunas faltando na planilha: {', '.join(faltando)}")

            else:

                idx = {col: cabecalho.index(col) for col in colunas_esperadas}

                linhas = list(ws.iter_rows(min_row=2, values_only=True))

                linhas_validas = [l for l in linhas if any(c for c in l if c is not None)]

                st.info(f"{len(linhas_validas)} questões encontradas no arquivo.")

                if st.button("✅ Confirmar Importação"):

                    conn = sqlite3.connect("banco.db")
                    cursor = conn.cursor()

                    importadas = 0
                    erros = []

                    for i, linha in enumerate(linhas_validas, start=2):

                        try:
                            # Tags: troca ponto-e-vírgula por quebra de linha
                            tags_raw = str(linha[idx["tags"]] or "").strip()
                            tags_fmt = "\n".join(
                                t.strip() for t in tags_raw.split(";") if t.strip()
                            )

                            cursor.execute("""
                            INSERT INTO questoes
                            (materia, assunto, banca, cargo, ano, dificuldade,
                             tags, questao, gabarito, comentario, observacoes, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(linha[idx["materia"]] or "").strip(),
                                str(linha[idx["assunto"]] or "").strip(),
                                str(linha[idx["banca"]] or "").strip(),
                                str(linha[idx["cargo"]] or "").strip(),
                                int(linha[idx["ano"]] or 2025),
                                str(linha[idx["dificuldade"]] or "Média").strip(),
                                tags_fmt,
                                str(linha[idx["questao"]] or "").strip(),
                                str(linha[idx["gabarito"]] or "Certo").strip(),
                                str(linha[idx["comentario"]] or "").strip(),
                                "",
                                "Não respondida"
                            ))

                            importadas += 1

                        except Exception as e:
                            erros.append(f"Linha {i}: {e}")

                    conn.commit()
                    conn.close()

                    st.success(f"✅ {importadas} questões importadas com sucesso!")

                    if erros:
                        st.warning("Algumas linhas tiveram erros:")
                        for erro in erros:
                            st.write(f"• {erro}")

        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

    st.divider()

    st.subheader("📄 Baixar Modelo de Planilha")

    if st.button("Gerar modelo Excel"):

        wb_modelo = openpyxl.Workbook()
        ws_modelo = wb_modelo.active
        ws_modelo.title = "Questoes"

        ws_modelo.append([
            "materia", "assunto", "banca", "cargo", "ano",
            "dificuldade", "tags", "questao", "gabarito", "comentario"
        ])

        ws_modelo.append([
            "Direito Civil", "Curatela", "CESPE", "Analista", 2024,
            "Média", "Curatela;Incapacidade",
            "A curatela é medida protetiva de caráter excepcional. (Certo/Errado)",
            "Certo", "Conforme art. 84 do Estatuto da Pessoa com Deficiência."
        ])

        caminho_modelo = "/tmp/modelo_questoes.xlsx"
        wb_modelo.save(caminho_modelo)

        with open(caminho_modelo, "rb") as f:
            st.download_button(
                label="⬇️ Baixar modelo.xlsx",
                data=f,
                file_name="modelo_questoes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ===================================================
# RESOLVER QUESTÕES
# ===================================================

elif menu == "Resolver Questões":

    st.header("Resolver Questões")

    materia_filtro = st.text_input("Matéria")

    cargo_filtro = st.text_input("Cargo")

    banca_filtro = st.text_input("Banca")

    ano_filtro = st.text_input("Ano")

    dificuldade_filtro = st.selectbox(
        "Dificuldade",
        ["", "Muito Fácil", "Fácil", "Média", "Difícil", "Muito Difícil", "Pegadinha"]
    )

    todas_tags = get_todas_tags()

    tags_filtro = st.multiselect(
        "Tags (pode escolher várias)",
        options=todas_tags
    )

    col1, col2 = st.columns(2)

    with col1:
        aleatoria = st.button("🎲 Questão Aleatória")

    with col2:
        buscar = st.button("🔍 Buscar Questão")

    if aleatoria:

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM questoes
        ORDER BY RANDOM()
        LIMIT 1
        """)

        st.session_state["questao"] = cursor.fetchone()
        conn.close()

    if buscar:

        sql = "SELECT * FROM questoes WHERE 1=1"
        parametros = []

        if materia_filtro:
            sql += " AND materia = ?"
            parametros.append(materia_filtro)

        if cargo_filtro:
            sql += " AND cargo = ?"
            parametros.append(cargo_filtro)

        if banca_filtro:
            sql += " AND banca = ?"
            parametros.append(banca_filtro)

        if ano_filtro:
            sql += " AND ano = ?"
            parametros.append(ano_filtro)

        if dificuldade_filtro:
            sql += " AND dificuldade = ?"
            parametros.append(dificuldade_filtro)

        for tag in tags_filtro:
            sql += " AND tags LIKE ?"
            parametros.append(f"%{tag}%")

        sql += " ORDER BY RANDOM() LIMIT 1"

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        st.session_state["questao"] = cursor.fetchone()
        conn.close()

    if "questao" in st.session_state and st.session_state["questao"]:

        registro = st.session_state["questao"]

        questao_id  = registro[0]
        materia     = registro[1]
        assunto     = registro[2]
        banca       = registro[3]
        cargo       = registro[4]
        ano         = registro[5]
        dificuldade = registro[6]
        tags        = registro[7]
        questao     = registro[8]
        gabarito    = registro[9]
        comentario  = registro[10]
        observacoes = registro[11]
        status      = registro[12]

        st.divider()

        st.write(questao)

        resposta = st.radio(
            "Sua resposta",
            ["Certo", "Errado"],
            index=None
        )

        if st.button("Responder"):

            if resposta == gabarito:
                st.success("✅ Você acertou!")
                novo_status = "Acertada"
            else:
                st.error("❌ Você errou!")
                novo_status = "Errada"

            conn = sqlite3.connect("banco.db")
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE questoes SET status = ? WHERE id = ?
            """, (novo_status, questao_id))

            atualizar_estatisticas_tag(cursor, tags, novo_status)

            conn.commit()
            conn.close()

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📖 Ver Comentário"):
                st.session_state["mostrar_comentario"] = True

        with col2:
            if st.button("📝 Minhas Observações"):
                st.session_state["mostrar_obs"] = True

        with col3:
            if st.button("🏷️ Ver Dados da Questão"):
                st.session_state["mostrar_dados"] = True

        if st.session_state.get("mostrar_comentario", False):
            st.subheader("Comentário")
            st.write(comentario)

        if st.session_state.get("mostrar_obs", False):

            observacao = st.text_area("Minhas Observações", value=observacoes)

            if st.button("Salvar Observação"):

                conn = sqlite3.connect("banco.db")
                cursor = conn.cursor()

                cursor.execute("""
                UPDATE questoes SET observacoes = ? WHERE id = ?
                """, (observacao, questao_id))

                conn.commit()
                conn.close()

                st.success("Observação salva.")

        if st.session_state.get("mostrar_dados", False):

            st.subheader("Dados da Questão")
            st.write(f"**Banca:** {banca}")
            st.write(f"**Cargo:** {cargo}")
            st.write(f"**Ano:** {ano}")
            st.write(f"**Dificuldade:** {dificuldade}")
            st.write("**Tags:**")

            for tag in tags.splitlines():
                if tag.strip():
                    st.write(f"• {tag}")


# ===================================================
# REVISAR QUESTÕES
# ===================================================

elif menu == "Revisar Questões":

    st.header("Revisar Questões")

    materia_filtro = st.text_input("Matéria", key="rev_materia")

    cargo_filtro = st.text_input("Cargo", key="rev_cargo")

    banca_filtro = st.text_input("Banca", key="rev_banca")

    ano_filtro = st.text_input("Ano", key="rev_ano")

    dificuldade_filtro = st.selectbox(
        "Dificuldade",
        ["", "Muito Fácil", "Fácil", "Média", "Difícil", "Muito Difícil", "Pegadinha"],
        key="rev_dificuldade"
    )

    status_filtro = st.selectbox(
        "Status",
        ["", "Não respondida", "Acertada", "Errada"],
        key="rev_status"
    )

    todas_tags = get_todas_tags()

    # Pré-preenche tags se vier de "Revisar Somente Esta Tag"
    default_tags = []
    if "tag_revisao" in st.session_state:
        tag_pre = st.session_state.pop("tag_revisao")
        if tag_pre in todas_tags:
            default_tags = [tag_pre]

    tags_filtro = st.multiselect(
        "Tags (pode escolher várias)",
        options=todas_tags,
        default=default_tags,
        key="rev_tags"
    )

    if st.button("🔍 Buscar Questões"):

        sql = "SELECT * FROM questoes WHERE 1=1"
        parametros = []

        if materia_filtro:
            sql += " AND materia = ?"
            parametros.append(materia_filtro)

        if cargo_filtro:
            sql += " AND cargo = ?"
            parametros.append(cargo_filtro)

        if banca_filtro:
            sql += " AND banca = ?"
            parametros.append(banca_filtro)

        if ano_filtro:
            sql += " AND ano = ?"
            parametros.append(ano_filtro)

        if dificuldade_filtro:
            sql += " AND dificuldade = ?"
            parametros.append(dificuldade_filtro)

        if status_filtro:
            sql += " AND status = ?"
            parametros.append(status_filtro)

        for tag in tags_filtro:
            sql += " AND tags LIKE ?"
            parametros.append(f"%{tag}%")

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        questoes_filtradas = cursor.fetchall()
        conn.close()

        st.session_state["questoes_revisao"] = questoes_filtradas
        st.session_state["indice_revisao"] = 0

    if (
        "questoes_revisao" in st.session_state
        and len(st.session_state["questoes_revisao"]) > 0
    ):

        total = len(st.session_state["questoes_revisao"])

        st.success(f"{total} questões encontradas.")

        indice = st.session_state["indice_revisao"]

        questao = st.session_state["questoes_revisao"][indice]

        questao_id  = questao[0]
        materia     = questao[1]
        assunto     = questao[2]
        banca       = questao[3]
        cargo       = questao[4]
        ano         = questao[5]
        dificuldade = questao[6]
        tags        = questao[7]
        texto       = questao[8]
        gabarito    = questao[9]
        comentario  = questao[10]
        observacoes = questao[11]
        status      = questao[12]

        st.divider()

        st.write(texto)

        resposta = st.radio(
            "Sua resposta",
            ["Certo", "Errado"],
            index=None,
            key=f"resp_{questao_id}"
        )

        if st.button("Responder Revisão"):

            if resposta == gabarito:
                novo_status = "Acertada"
                st.success("✅ Você acertou!")
            else:
                novo_status = "Errada"
                st.error("❌ Você errou!")

            conn = sqlite3.connect("banco.db")
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE questoes SET status = ? WHERE id = ?
            """, (novo_status, questao_id))

            atualizar_estatisticas_tag(cursor, tags, novo_status)

            conn.commit()
            conn.close()

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📖 Comentário", key=f"coment_{questao_id}"):
                st.session_state["mostrar_comentario_rev"] = True

        with col2:
            if st.button("📝 Observações", key=f"obs_{questao_id}"):
                st.session_state["mostrar_obs_rev"] = True

        with col3:
            if st.button("🏷️ Dados", key=f"dados_{questao_id}"):
                st.session_state["mostrar_dados_rev"] = True

        if st.session_state.get("mostrar_comentario_rev", False):
            st.subheader("Comentário")
            st.write(comentario)

        if st.session_state.get("mostrar_obs_rev", False):

            observacao = st.text_area(
                "Minhas Observações",
                value=observacoes,
                key=f"obs_text_{questao_id}"
            )

            if st.button("Salvar Observação", key=f"salvar_obs_{questao_id}"):

                conn = sqlite3.connect("banco.db")
                cursor = conn.cursor()

                cursor.execute("""
                UPDATE questoes SET observacoes = ? WHERE id = ?
                """, (observacao, questao_id))

                conn.commit()
                conn.close()

                st.success("Observação salva.")

        if st.session_state.get("mostrar_dados_rev", False):

            st.subheader("Dados da Questão")
            st.write(f"**Banca:** {banca}")
            st.write(f"**Cargo:** {cargo}")
            st.write(f"**Ano:** {ano}")
            st.write(f"**Dificuldade:** {dificuldade}")
            st.write("**Tags:**")

            for tag in tags.splitlines():
                if tag.strip():
                    st.write(f"• {tag}")

        col1, col2 = st.columns(2)

        with col1:
            if indice > 0 and st.button("⬅️ Anterior"):
                st.session_state["indice_revisao"] -= 1
                st.rerun()

        with col2:
            if indice < total - 1 and st.button("➡️ Próxima"):
                st.session_state["indice_revisao"] += 1
                st.rerun()


# ===================================================
# ESTATÍSTICAS
# ===================================================

elif menu == "Estatísticas":

    st.header("Estatísticas por Tag")

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    lista_tags = get_todas_tags()

    if not lista_tags:

        st.warning("Nenhuma tag cadastrada.")

    else:

        tag_escolhida = st.selectbox("Escolha uma Tag", lista_tags)

        cursor.execute("""
        SELECT DISTINCT ciclo
        FROM estatisticas_tag
        WHERE tag = ?
        ORDER BY ciclo
        """, (tag_escolhida,))

        ciclos = [item[0] for item in cursor.fetchall()]

        if not ciclos:
            ciclos = [1]
            cursor.execute("""
            INSERT INTO estatisticas_tag (tag, ciclo, acertos, erros)
            VALUES (?, ?, 0, 0)
            """, (tag_escolhida, 1))
            conn.commit()

        ciclo_escolhido = st.selectbox("Ciclo", ciclos)

        cursor.execute("""
        SELECT acertos, erros
        FROM estatisticas_tag
        WHERE tag = ? AND ciclo = ?
        """, (tag_escolhida, ciclo_escolhido))

        resultado = cursor.fetchone()

        if resultado:
            acertos = resultado[0]
            erros   = resultado[1]
        else:
            acertos = 0
            erros   = 0

        total = acertos + erros

        percentual = (acertos / total * 100) if total > 0 else 0

        if percentual <= 50:
            dominio = "🔴 Crítico"
        elif percentual <= 70:
            dominio = "🟠 Fraco"
        elif percentual <= 85:
            dominio = "🟡 Bom"
        elif percentual <= 95:
            dominio = "🟢 Muito Bom"
        else:
            dominio = "🏆 Dominado"

        st.divider()

        st.subheader(f"🏷️ {tag_escolhida}")
        st.write(f"🔥 Nível de domínio: {dominio}")
        st.write(f"📚 Ciclo: {ciclo_escolhido}")

        cursor.execute("""
        SELECT COUNT(*)
        FROM questoes
        WHERE tags LIKE ?
        """, (f"%{tag_escolhida}%",))

        total_questoes_tag = cursor.fetchone()[0]

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total da Tag", total_questoes_tag)

        with col2:
            st.metric("Questões do Ciclo", total)

        with col3:
            st.metric("Acertos", acertos)

        with col4:
            st.metric("Erros", erros)

        with col5:
            st.metric("% Acerto", f"{percentual:.2f}%")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📚 Revisar Somente Esta Tag"):
                st.session_state["tag_revisao"] = tag_escolhida
                st.session_state["menu_override"] = "Revisar Questões"
                st.session_state["rev_status"] = ""
                st.rerun()

        with col2:
            if st.button("🔄 Criar Novo Ciclo"):

                novo_ciclo = max(ciclos) + 1

                cursor.execute("""
                INSERT INTO estatisticas_tag (tag, ciclo, acertos, erros)
                VALUES (?, ?, 0, 0)
                """, (tag_escolhida, novo_ciclo))

                cursor.execute("""
                UPDATE questoes
                SET status = 'Não respondida'
                WHERE tags LIKE ?
                """, (f"%{tag_escolhida}%",))

                conn.commit()

                st.success(f"Ciclo {novo_ciclo} criado.")

                st.rerun()

    conn.close()


# ===================================================
# DASHBOARD VISUAL
# ===================================================

elif menu == "Dashboard":

    st.header("📊 Dashboard das Tags")

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    lista_tags = get_todas_tags()

    if not lista_tags:
        st.warning("Nenhuma tag cadastrada ainda.")
        conn.close()

    else:

        # Para cada tag pega o ciclo mais recente
        dados = []

        for tag in lista_tags:

            cursor.execute("""
            SELECT ciclo, acertos, erros
            FROM estatisticas_tag
            WHERE tag = ?
            ORDER BY ciclo DESC
            LIMIT 1
            """, (tag,))

            linha = cursor.fetchone()

            if linha:
                ciclo, acertos, erros = linha
            else:
                ciclo, acertos, erros = 1, 0, 0

            total = acertos + erros
            pct = (acertos / total * 100) if total > 0 else 0

            if pct <= 50:
                cor = "#e74c3c"    # vermelho
            elif pct <= 70:
                cor = "#e67e22"    # laranja
            elif pct <= 85:
                cor = "#f1c40f"    # amarelo
            elif pct <= 95:
                cor = "#2ecc71"    # verde
            else:
                cor = "#1abc9c"    # verde escuro

            cursor.execute("""
            SELECT COUNT(*) FROM questoes WHERE tags LIKE ?
            """, (f"%{tag}%",))

            total_banco = cursor.fetchone()[0]

            dados.append({
                "tag": tag,
                "ciclo": ciclo,
                "acertos": acertos,
                "erros": erros,
                "total_ciclo": total,
                "pct": pct,
                "total_banco": total_banco,
                "cor": cor,
            })

        conn.close()

        # --- Gráfico de barras: % acerto por tag ---
        st.subheader("% de Acerto por Tag (ciclo mais recente)")

        tags_labels  = [d["tag"] for d in dados]
        pcts         = [d["pct"] for d in dados]
        cores        = [d["cor"] for d in dados]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=tags_labels,
            y=pcts,
            marker_color=cores,
            text=[f"{p:.1f}%" for p in pcts],
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "% Acerto: %{y:.1f}%<br>"
                "<extra></extra>"
            )
        ))

        fig.add_hline(
            y=70,
            line_dash="dot",
            line_color="orange",
            annotation_text="Meta mínima (70%)",
            annotation_position="bottom right"
        )

        fig.update_layout(
            yaxis=dict(title="% Acerto", range=[0, 110]),
            xaxis=dict(title="Tag"),
            showlegend=False,
            height=420,
            margin=dict(t=40, b=60),
        )

        st.plotly_chart(fig, use_container_width=True)

        # --- Gráfico de barras empilhadas: acertos vs erros ---
        st.subheader("Acertos vs Erros por Tag")

        fig2 = go.Figure()

        fig2.add_trace(go.Bar(
            name="Acertos",
            x=tags_labels,
            y=[d["acertos"] for d in dados],
            marker_color="#2ecc71",
        ))

        fig2.add_trace(go.Bar(
            name="Erros",
            x=tags_labels,
            y=[d["erros"] for d in dados],
            marker_color="#e74c3c",
        ))

        fig2.update_layout(
            barmode="stack",
            yaxis=dict(title="Questões"),
            xaxis=dict(title="Tag"),
            height=380,
            margin=dict(t=40, b=60),
        )

        st.plotly_chart(fig2, use_container_width=True)

        # --- Tabela resumo ---
        st.subheader("Resumo por Tag")

        st.markdown(
            "| Tag | Ciclo | Total no Banco | Respondidas | Acertos | Erros | % Acerto | Domínio |"
        )
        st.markdown(
            "|-----|-------|---------------|-------------|---------|-------|----------|---------|"
        )

        for d in dados:
            pct = d["pct"]
            if pct <= 50:
                dom = "🔴 Crítico"
            elif pct <= 70:
                dom = "🟠 Fraco"
            elif pct <= 85:
                dom = "🟡 Bom"
            elif pct <= 95:
                dom = "🟢 Muito Bom"
            else:
                dom = "🏆 Dominado"

            st.markdown(
                f"| {d['tag']} | {d['ciclo']} | {d['total_banco']} "
                f"| {d['total_ciclo']} | {d['acertos']} | {d['erros']} "
                f"| {pct:.1f}% | {dom} |"
            )