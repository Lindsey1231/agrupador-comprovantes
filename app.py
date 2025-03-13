import streamlit as st
import os
import tempfile
import re
import difflib
import shutil
import zipfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar o nome do fornecedor e valores."""
    try:
        reader = PdfReader(arquivo)
        texto = " \n".join([page.extract_text() or "" for page in reader.pages])
        return texto
    except:
        return ""

def encontrar_nome_fornecedor(texto):
    """Busca um nome de fornecedor no conteúdo do PDF, considerando maiúsculas e minúsculas."""
    padrao = re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ&\s]+(?:ltda|s\.a\.|me|eireli|ss|associação|empresa|corporation|corp|inc)?)", re.IGNORECASE)
    correspondencias = padrao.findall(texto)
    if correspondencias:
        return correspondencias[0].strip()
    return ""

def encontrar_valor(texto):
    """Busca valores monetários no PDF para comparação entre comprovantes e documentos principais."""
    padrao = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")  # Formato 1.234,56
    correspondencias = padrao.findall(texto)
    if correspondencias:
        return set(correspondencias)  # Retorna um conjunto de valores únicos
    return set()

def comparar_nomes(nome1, nome2):
    """Compara dois nomes e retorna um índice de similaridade."""
    return difflib.SequenceMatcher(None, nome1.lower(), nome2.lower()).ratio()

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    fornecedores = {}
    comprovantes = []
    st.write("### Arquivos detectados:")
    
    # Identifica os documentos principais (NF, boleto, invoice ou guia)
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        valores_pdf = encontrar_valor(texto_pdf)
        
        if nome.startswith("(BTG)") or nome.startswith("(INTER)") or nome.startswith("(BV)"):
            fornecedor_nome = encontrar_nome_fornecedor(texto_pdf)
            if fornecedor_nome:
                agrupados[nome] = {"nf": arquivo, "comprovantes": [], "fornecedor": fornecedor_nome, "valores": valores_pdf}
                fornecedores[fornecedor_nome.lower()] = nome
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL para {fornecedor_nome}")
        elif nome.lower().startswith("pix"):
            comprovantes.append((arquivo, texto_pdf, valores_pdf))
    
    # Associa os comprovantes de pagamento aos documentos principais
    for arquivo, texto_pdf, valores_comprovante in comprovantes:
        nome = arquivo.name
        fornecedor_encontrado = encontrar_nome_fornecedor(texto_pdf)
        melhor_match = None
        maior_similaridade = 0.0

        for fornecedor, chave in fornecedores.items():
            valores_nf = agrupados[chave]["valores"]
            
            # Primeiro, tenta associar pelo valor
            if valores_comprovante & valores_nf:  # Se houver valores em comum
                agrupados[chave]["comprovantes"].append(arquivo)
                st.write(f"🔗 {nome} associado a {chave} pelo valor correspondente")
                break
            # Se não encontrar pelo valor, tenta associar pelo nome com similaridade
            similaridade = comparar_nomes(fornecedor_encontrado, fornecedor)
            if similaridade > maior_similaridade:  # Pega o melhor match
                melhor_match = chave
                maior_similaridade = similaridade
        
        # Se encontrou um nome similar, faz a associação
        if melhor_match and maior_similaridade > 0.7:  # Usa um limite de 70% de similaridade
            agrupados[melhor_match]["comprovantes"].append(arquivo)
            st.write(f"🔗 {nome} associado a {melhor_match} pelo nome do fornecedor (similaridade {maior_similaridade:.2f})")
    
    pdf_resultados = {}
    temp_zip_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tempfile.gettempdir(), "comprovantes_agrupados.zip")
    
    # Criar PDFs finais para cada fornecedor
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for chave, docs in agrupados.items():
            if docs["comprovantes"]:
                merger = PdfMerger()
                arquivos_adicionados = set()
                
                for pdf in docs["comprovantes"] + [docs["nf"]]:
                    if pdf and pdf.name not in arquivos_adicionados:
                        temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                        with open(temp_path, "wb") as temp_file:
                            temp_file.write(pdf.getbuffer())  
                        merger.append(temp_path)
                        arquivos_adicionados.add(pdf.name)
                
                nome_arquivo_final = docs["nf"].name  # Mantém o nome original do documento principal
                caminho_saida = os.path.join(temp_zip_dir, nome_arquivo_final)
                merger.write(caminho_saida)
                merger.close()
                zipf.write(caminho_saida, arcname=nome_arquivo_final)
                st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
            else:
                st.warning(f"⚠️ Nenhum comprovante encontrado para {docs['nf'].name}")
    
    return zip_path

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")
    
    if st.button("Juntar PDFs e baixar ZIP"):
        st.write("🔄 Processando arquivos... Aguarde.")
        zip_resultado = organizar_por_fornecedor(uploaded_files)

        if not zip_resultado:
            st.error("Nenhum arquivo foi processado. Verifique os nomes e tente novamente.")
        else:
            with open(zip_resultado, "rb") as file:
                st.download_button(
                    label="Baixar todos os PDFs em ZIP",
                    data=file,
                    file_name="comprovantes_agrupados.zip",
                    mime="application/zip"
                )
