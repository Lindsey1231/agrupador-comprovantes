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

def organizar_por_cnpj_e_valor(arquivos):
    st.write("### Processando arquivos...")
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
    pdf_resultados = {}
    agrupados = {}
    info_arquivos = []
    nao_agrupados = []
    
    # Extrai informações dos arquivos
    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        valores = encontrar_valor(texto_pdf)
        cnpjs = encontrar_cnpj(texto_pdf)
        cpfs = encontrar_cpf(texto_pdf)
        tipo_arquivo = classificar_arquivo(nome)
        info_arquivos.append((arquivo, nome, valores, cnpjs, cpfs, tipo_arquivo))
    
    # Associa documentos e comprovantes
    for doc, nome_doc, valores_doc, cnpjs_doc, cpfs_doc, tipo_doc in info_arquivos:
        if tipo_doc != "documento":
            continue
        
        melhor_correspondencia = None
        
        # 1. Tenta correspondência por CNPJ/CPF e valor
        for comprovante, nome_comp, valores_comp, cnpjs_comp, cpfs_comp, tipo_comp in info_arquivos:
            if tipo_comp == "comprovante" and (bool(cnpjs_comp & cnpjs_doc) or bool(cpfs_comp & cpfs_doc)):
                if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                    melhor_correspondencia = comprovante
                    break
        
        # 2. Se não encontrou por CNPJ/CPF e valor, tenta apenas por CNPJ/CPF
        if not melhor_correspondencia:
            for comprovante, nome_comp, valores_comp, cnpjs_comp, cpfs_comp, tipo_comp in info_arquivos:
                if tipo_comp == "comprovante" and (bool(cnpjs_comp & cnpjs_doc) or bool(cpfs_comp & cpfs_doc)):
                    melhor_correspondencia = comprovante
                    break
        
        # 3. Se ainda não encontrou, tenta apenas por valor
        if not melhor_correspondencia:
            for comprovante, nome_comp, valores_comp, cnpjs_comp, cpfs_comp, tipo_comp in info_arquivos:
                if tipo_comp == "comprovante":
                    if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                        melhor_correspondencia = comprovante
                        break
        
        if melhor_correspondencia:
            agrupados[nome_doc] = [melhor_correspondencia, doc]
            info_arquivos = [(a, n, v, cnpj, cpf, t) for a, n, v, cnpj, cpf, t in info_arquivos if a != melhor_correspondencia]
    
    # Identifica comprovantes não agrupados
    for comprovante, nome_comp, valores_comp, cnpjs_comp, cpfs_comp, tipo_comp in info_arquivos:
        if tipo_comp == "comprovante":
            # Determina o que foi encontrado
            tem_documento = bool(cnpjs_comp or cpfs_comp)
            tem_valor = bool(valores_comp)
            
            if tem_documento and tem_valor:
                status = "CNPJ/CPF + VALOR"
            elif tem_documento:
                status = "APENAS CNPJ/CPF"
            elif tem_valor:
                status = "APENAS VALOR"
            else:
                status = "NENHUM DADO RELEVANTE"
            
            nao_agrupados.append((nome_comp, status))
            nome_referencia = f"Sem Correspondência - {nome_comp}"
            agrupados[nome_referencia] = [comprovante]
    
    # Mostra resumo dos não agrupados
    if nao_agrupados:
        st.write("### 📊 Resumo dos Comprovantes Não Agrupados")
        for nome, status in nao_agrupados:
            st.write(f"- **{nome}**: {status}")
    
    # Gera PDFs agrupados e arquivo ZIP
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for nome_final, arquivos in agrupados.items():
            merger = PdfMerger()
            for doc in arquivos:
                merger.append(doc)
            output_filename = nome_final
            output_path = os.path.join(temp_dir, output_filename)
            merger.write(output_path)
            merger.close()
            pdf_resultados[output_filename] = output_path
            zipf.write(output_path, arcname=output_filename)
    
    return pdf_resultados, zip_path

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True, key="file_uploader")
    
    if arquivos and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs", key="process_button"):
            pdf_resultados, zip_path = organizar_por_cnpj_e_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(
                        label=f"📄 Baixar {nome}",
                        data=f,
                        file_name=nome,
                        mime="application/pdf",
                        key=f"download_{nome}"
                    )
            
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="📥 Baixar todos como ZIP",
                    data=f,
                    file_name="comprovantes_agrupados.zip",
                    mime="application/zip",
                    key="download_zip"
                )

if __name__ == "__main__":
    main()
