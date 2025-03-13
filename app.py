import streamlit as st
import os
import tempfile
import re
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar o nome do fornecedor."""
    try:
        reader = PdfReader(arquivo)
        texto = " \n".join([page.extract_text() or "" for page in reader.pages])
        return texto.lower()
    except:
        return ""

def encontrar_nome_fornecedor(texto):
    """Busca o primeiro nome do fornecedor no conteúdo do PDF."""
    padrao = re.compile(r"(\b[A-Z][a-z]+\b)")  # Pega o primeiro nome que começa com letra maiúscula
    correspondencias = padrao.findall(texto)
    if correspondencias:
        return correspondencias[0].strip()
    return ""

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    fornecedores = {}
    comprovantes = []
    st.write("### Arquivos detectados:")
    
    # Identifica os documentos principais (NF, boleto ou invoice)
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        
        if nome.startswith("(BTG)") or nome.startswith("(INTER)") or nome.startswith("(BV)"):
            fornecedor_nome = encontrar_nome_fornecedor(texto_pdf)
            if fornecedor_nome:
                agrupados[nome] = {"nf": arquivo, "comprovantes": [], "fornecedor": fornecedor_nome}
                fornecedores[fornecedor_nome.lower()] = nome
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL para {fornecedor_nome}")
        elif nome.lower().startswith("pix"):
            comprovantes.append((arquivo, texto_pdf))
    
    # Associa os comprovantes de pagamento aos documentos principais
    for arquivo, texto_pdf in comprovantes:
        nome = arquivo.name
        fornecedor_encontrado = encontrar_nome_fornecedor(texto_pdf)
        
        for fornecedor, chave in fornecedores.items():
            if fornecedor_encontrado and fornecedor_encontrado.lower() in fornecedor and chave in agrupados:
                agrupados[chave]["comprovantes"].append(arquivo)
                st.write(f"🔗 {nome} associado a {chave}")
                break
    
    pdf_resultados = {}
    
    # Criar PDFs finais para cada fornecedor
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
            caminho_saida = os.path.join(tempfile.gettempdir(), nome_arquivo_final)
            merger.write(caminho_saida)
            merger.close()
            pdf_resultados[chave] = caminho_saida
            st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
        else:
            st.warning(f"⚠️ Nenhum comprovante encontrado para {docs['nf'].name}")
    
    return pdf_resultados

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")
    
    if st.button("Juntar PDFs"):
        st.write("🔄 Processando arquivos... Aguarde.")
        resultados = organizar_por_fornecedor(uploaded_files)

        if not resultados:
            st.error("Nenhum arquivo foi processado. Verifique os nomes e tente novamente.")

        for chave, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {chave}",
                    data=file,
                    file_name=chave,
                    mime="application/pdf"
                )
