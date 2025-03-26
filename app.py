import streamlit as st
import os
import tempfile
import re
import zipfile
from PyPDF2 import PdfMerger, PdfReader
import pytesseract
from pdf2image import convert_from_path

# Definindo o caminho do Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\lindsey.silva\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Definindo o caminho do Poppler
POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF, usando OCR se necessário."""
    try:
        # Criar um arquivo temporário para armazenar o PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(arquivo.getbuffer())
            temp_pdf_path = temp_pdf.name

        reader = PdfReader(temp_pdf_path)
        texto = []
        
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texto.append(page_text)
            else:
                images = convert_from_path(temp_pdf_path, poppler_path=POPPLER_PATH)
                for image in images:
                    texto.append(pytesseract.image_to_string(image, lang='por'))
        
        os.remove(temp_pdf_path)
        return " \n".join(texto)
    except Exception as e:
        st.error(f"Erro na extração do texto do arquivo {arquivo.name}: {str(e)}")
        return ""

def encontrar_valor(texto):
    """Busca valores monetários no conteúdo do PDF."""
    padrao_valor = re.findall(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})\b", texto)
    valores_processados = set()
    for valor in padrao_valor:
        try:
            valores_processados.add(float(valor.replace('.', '').replace(',', '.')))
        except ValueError:
            continue
    return valores_processados

def encontrar_cnpj(texto):
    """Busca CNPJs no conteúdo do PDF e padroniza a formatação."""
    padrao_cnpj = re.findall(r"\b\d{2}[.\/]?\d{3}[.\/]?\d{3}[\/\-]?\d{4}[\/\-]?\d{2}\b", texto)
    cnpjs = {re.sub(r'[^\d]', '', cnpj) for cnpj in padrao_cnpj} if padrao_cnpj else set()
    cnpjs_ignorados = {"19307785000178", "45121046000105", "28932155000185"}
    return cnpjs - cnpjs_ignorados

def encontrar_cpf(texto):
    """Busca CPFs no conteúdo do PDF e padroniza a formatação."""
    padrao_cpf = re.findall(r"\b\d{3}[.\-]?\d{3}[.\-]?\d{3}[.\-]?\d{2}\b", texto)
    cpfs = {re.sub(r'[^\d]', '', cpf) for cpf in padrao_cpf} if padrao_cpf else set()
    return cpfs

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo baseado no nome."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def formatar_saida(nome, cnpjs, cpfs, valores):
    """Formata a saída como solicitado: (CNPJ; VALOR)"""
    doc = list(cnpjs)[0] if cnpjs else (list(cpfs)[0] if cpfs else None)
    valor = list(valores)[0] if valores else None
    
    # Formatar CNPJ/CPF
    if doc:
        doc_formatado = re.sub(r'(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})', r'\1.\2.\3/\4-\5', doc) if len(doc) == 14 else \
                       re.sub(r'(\d{3})(\d{3})(\d{3})(\d{2})', r'\1.\2.\3-\4', doc)
    else:
        doc_formatado = "N/A"
    
    # Formatar valor
    if valor:
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        valor_formatado = "N/A"
    
    return f"{nome} ({doc_formatado}; {valor_formatado})"

def organizar_por_cnpj_e_valor(arquivos):
    st.write("### Processando arquivos...")
    
    try:
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
        pdf_resultados = {}
        agrupados = {}
        info_arquivos = []
        
        # Verificação dos arquivos
        st.write("### Verificação dos Arquivos")
        for arquivo in arquivos:
            nome = arquivo.name
            texto_pdf = extrair_texto_pdf(arquivo)
            valores = encontrar_valor(texto_pdf)
            cnpjs = encontrar_cnpj(texto_pdf)
            cpfs = encontrar_cpf(texto_pdf)
            
            st.code(formatar_saida(nome, cnpjs, cpfs, valores), language='text')
            tipo_arquivo = classificar_arquivo(nome)
            info_arquivos.append((arquivo, nome, valores, cnpjs, cpfs, tipo_arquivo))
        
        # [Seu código original de agrupamento aqui...]
        
        # Gera os PDFs agrupados e o ZIP
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for nome_final, arquivos_agrupados in agrupados.items():
                merger = PdfMerger()
                output_path = os.path.join(temp_dir, nome_final)
                
                for doc in arquivos_agrupados:
                    merger.append(doc)
                
                merger.write(output_path)
                merger.close()
                
                # Adiciona ao ZIP
                zipf.write(output_path, arcname=nome_final)
                # Armazena para download individual
                pdf_resultados[nome_final] = output_path
                
                st.write(f"📂 Arquivo gerado: {nome_final}")
        
        return pdf_resultados, zip_path
        
    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")
        return {}, None

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True, key="file_uploader")
    
    if arquivos and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs", key="process_button"):
            pdf_resultados, zip_path = organizar_por_cnpj_e_valor(arquivos)
            
            if pdf_resultados:
                st.write("### 📥 Downloads Individuais")
                cols = st.columns(2)  # Cria 2 colunas para organizar os botões
                
                for i, (nome, caminho) in enumerate(pdf_resultados.items()):
                    with open(caminho, "rb") as f:
                        # Alterna entre as colunas para melhor organização
                        with cols[i % 2]:
                            st.download_button(
                                label=f"⬇️ {nome}",
                                data=f,
                                file_name=nome,
                                mime="application/pdf",
                                key=f"indiv_{nome}"
                            )
                
                st.write("---")
                st.write("### 📦 Pacote Completo")
                if zip_path and os.path.exists(zip_path):
                    with open(zip_path, "rb") as f:
                        st.download_button(
                            label="📥 Baixar TODOS como ZIP",
                            data=f,
                            file_name="comprovantes_agrupados.zip",
                            mime="application/zip",
                            key="download_zip_all"
                        )
                else:
                    st.warning("Arquivo ZIP não foi gerado")
            else:
                st.warning("Nenhum arquivo foi gerado para download")
