import streamlit as st
import os
import tempfile
import re
import zipfile
from PyPDF2 import PdfMerger, PdfReader
import pytesseract
from pdf2image import convert_from_path

# Configurações (ajuste os caminhos conforme necessário)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\lindsey.silva\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF, usando OCR se necessário."""
    try:
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
        st.error(f"Erro na extração do texto: {str(e)}")
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
    """Busca CNPJs no conteúdo do PDF."""
    padrao_cnpj = re.findall(r"\b\d{2}[.\/]?\d{3}[.\/]?\d{3}[\/\-]?\d{4}[\/\-]?\d{2}\b", texto)
    cnpjs = {re.sub(r'[^\d]', '', cnpj) for cnpj in padrao_cnpj} if padrao_cnpj else set()
    cnpjs_ignorados = {"19307785000178", "45121046000105", "28932155000185"}
    return cnpjs - cnpjs_ignorados

def encontrar_cpf(texto):
    """Busca CPFs no conteúdo do PDF."""
    padrao_cpf = re.findall(r"\b\d{3}[.\-]?\d{3}[.\-]?\d{3}[.\-]?\d{2}\b", texto)
    cpfs = {re.sub(r'[^\d]', '', cpf) for cpf in padrao_cpf} if padrao_cpf else set()
    return cpfs

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def formatar_saida(nome, cnpjs, cpfs, valores):
    """Formata a saída como (CNPJ/CPF; VALOR)."""
    doc = list(cnpjs)[0] if cnpjs else (list(cpfs)[0] if cpfs else None)
    valor = list(valores)[0] if valores else None
    
    # Formatar documento
    if doc:
        if len(doc) == 14:  # CNPJ
            doc_formatado = f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        else:  # CPF
            doc_formatado = f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    else:
        doc_formatado = "N/A"
    
    # Formatar valor
    if valor:
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        valor_formatado = "N/A"
    
    return f"{nome} ({doc_formatado}; {valor_formatado})"

def organizar_por_cnpj_e_valor(arquivos):
    """Processa e agrupa os arquivos."""
    try:
        temp_dir = tempfile.mkdtemp()
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
        
        st.write("### Verificação dos Arquivos")
        info_arquivos = []
        for arquivo in arquivos:
            texto = extrair_texto_pdf(arquivo)
            valores = encontrar_valor(texto)
            cnpjs = encontrar_cnpj(texto)
            cpfs = encontrar_cpf(texto)
            st.code(formatar_saida(arquivo.name, cnpjs, cpfs, valores), language='text')
            info_arquivos.append((arquivo, arquivo.name, valores, cnpjs, cpfs, classificar_arquivo(arquivo.name)))
        
        # Processamento de agrupamento (simplificado para exemplo)
        agrupados = {"Exemplo_Agrupado.pdf": arquivos[:1]}  # Exemplo simplificado
        
        # Gera arquivos PDF e ZIP
        pdf_resultados = {}
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for nome, arquivos_agrupados in agrupados.items():
                merger = PdfMerger()
                output_path = os.path.join(temp_dir, nome)
                
                for doc in arquivos_agrupados:
                    merger.append(doc)
                
                merger.write(output_path)
                merger.close()
                pdf_resultados[nome] = output_path
                zipf.write(output_path, arcname=nome)
        
        return pdf_resultados, zip_path
    
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        return {}, None

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True)
    
    if arquivos and st.button("🔗 Juntar e Processar PDFs"):
        pdf_resultados, zip_path = organizar_por_cnpj_e_valor(arquivos)
        
        if pdf_resultados:
            st.write("### 📥 Downloads Individuais")
            cols = st.columns(2)
            
            for i, (nome, caminho) in enumerate(pdf_resultados.items()):
                if os.path.exists(caminho):
                    with cols[i % 2]:
                        with open(caminho, "rb") as f:
                            st.download_button(
                                label=f"⬇️ {nome}",
                                data=f,
                                file_name=nome,
                                mime="application/pdf"
                            )
            
            st.write("---")
            st.write("### 📦 Pacote Completo")
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="📥 Baixar TODOS como ZIP",
                        data=f,
                        file_name="comprovantes_agrupados.zip",
                        mime="application/zip"
                    )
            else:
                st.warning("Arquivo ZIP não foi gerado")
        else:
            st.warning("Nenhum arquivo foi gerado para download")

if __name__ == "__main__":
    main()
