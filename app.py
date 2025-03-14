import streamlit as st
import os
import tempfile
import re
import zipfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF garantindo melhor leitura."""
    try:
        reader = PdfReader(arquivo)
        texto = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texto.append(page_text)
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

def encontrar_valor_total_reembolso(texto):
    """Busca o valor total em arquivos de reembolso."""
    # Padrão para encontrar o valor total no formato "BRL 100,00"
    padrao_valor_total = re.search(r"Total:\s*BRL\s*([\d.,]+)", texto)
    if padrao_valor_total:
        try:
            return float(padrao_valor_total.group(1).replace('.', '').replace(',', '.'))
        except ValueError:
            return None
    return None

def encontrar_cnpj(texto):
    """Busca CNPJs no conteúdo do PDF e padroniza a formatação."""
    padrao_cnpj = re.findall(r"\b\d{2}[.\/]?\d{3}[.\/]?\d{3}[\/\-]?\d{4}[\/\-]?\d{2}\b", texto)
    cnpjs = {re.sub(r'[^\d]', '', cnpj) for cnpj in padrao_cnpj} if padrao_cnpj else set()
    
    # Remove CNPJs que devem ser ignorados
    cnpjs_ignorados = {"19307785000178", "45121046000105", "28932155000185"}
    return cnpjs - cnpjs_ignorados

def encontrar_cpf(texto):
    """Busca CPFs no conteúdo do PDF e padroniza a formatação."""
    padrao_cpf = re.findall(r"\b\d{3}[.\-]?\d{3}[.\-]?\d{3}[.\-]?\d{2}\b", texto)
    cpfs = {re.sub(r'[^\d]', '', cpf) for cpf in padrao_cpf} if padrao_cpf else set()
    return cpfs

def encontrar_nome_beneficiario(texto):
    """Busca o nome do beneficiário no conteúdo do PDF."""
    padrao_nome = re.search(r"Favorecido\s*Nome:\s*([A-Z\s]+)", texto)
    if padrao_nome:
        return padrao_nome.group(1).strip()
    return None

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo baseado no nome."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def organizar_por_cnpj_cpf_e_valor(arquivos):
    st.write("### Processando arquivos...")
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
    pdf_resultados = {}
    agrupados = {}
    info_arquivos = []
    
    # Extrai informações dos arquivos
    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        valores = encontrar_valor(texto_pdf)
        valor_total_reembolso = encontrar_valor_total_reembolso(texto_pdf)
        cnpjs = encontrar_cnpj(texto_pdf)
        cpfs = encontrar_cpf(texto_pdf)
        nome_beneficiario = encontrar_nome_beneficiario(texto_pdf)
        tipo_arquivo = classificar_arquivo(nome)
        info_arquivos.append((arquivo, nome, valores, valor_total_reembolso, cnpjs, cpfs, nome_beneficiario, tipo_arquivo))
    
    # Agrupa documentos e comprovantes por CNPJ, CPF ou nome do beneficiário
    grupos_identificacao = {}
    for arquivo, nome, valores, valor_total_reembolso, cnpjs, cpfs, nome_beneficiario, tipo_arquivo in info_arquivos:
        identificacoes = list(cnpjs) + list(cpfs)  # Combina CNPJs e CPFs
        if nome_beneficiario:
            identificacoes.append(nome_beneficiario)  # Adiciona o nome do beneficiário
        for identificacao in identificacoes:
            if identificacao not in grupos_identificacao:
                grupos_identificacao[identificacao] = {"documentos": [], "comprovantes": []}
            if tipo_arquivo == "documento":
                grupos_identificacao[identificacao]["documentos"].append((arquivo, nome, valores, valor_total_reembolso, nome_beneficiario))
            elif tipo_arquivo == "comprovante":
                grupos_identificacao[identificacao]["comprovantes"].append((arquivo, nome, valores, nome_beneficiario))
    
    # Associa documentos e comprovantes
    for identificacao, grupo in grupos_identificacao.items():
        documentos = grupo["documentos"]
        comprovantes = grupo["comprovantes"]
        
        # Se houver mais de um documento ou comprovante para o mesmo CNPJ/CPF/nome, avalia CNPJ/CPF/nome + valor
        if len(documentos) > 1 or len(comprovantes) > 1:
            for doc, nome_doc, valores_doc, valor_total_reembolso_doc, nome_beneficiario_doc in documentos:
                melhor_correspondencia = None
                
                # Tenta correspondência por valor total do reembolso
                if valor_total_reembolso_doc:
                    for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in comprovantes:
                        if any(abs(vc - valor_total_reembolso_doc) / valor_total_reembolso_doc <= 0.005 for vc in valores_comp):
                            melhor_correspondencia = comprovante
                            break
                
                # Se não encontrou por valor total, tenta por valores individuais
                if not melhor_correspondencia:
                    for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in comprovantes:
                        if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                            melhor_correspondencia = comprovante
                            break
                
                # Se encontrou correspondência, adiciona ao grupo
                if melhor_correspondencia:
                    agrupados[nome_doc] = [melhor_correspondencia, doc]
                    # Remove o comprovante da lista para evitar duplicação
                    comprovantes.remove((melhor_correspondencia, nome_comp, valores_comp, nome_beneficiario_comp))
        else:
            # Para casos com apenas um documento e/ou comprovante, mantém a lógica original (CNPJ/CPF/nome primeiro, valor depois)
            for doc, nome_doc, valores_doc, valor_total_reembolso_doc, nome_beneficiario_doc in documentos:
                melhor_correspondencia = None
                
                # Tenta correspondência por CNPJ/CPF/nome
                for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in comprovantes:
                    if (identificacao in encontrar_cnpj(extrair_texto_pdf(comprovante))) or \
                       (identificacao in encontrar_cpf(extrair_texto_pdf(comprovante))) or \
                       (nome_beneficiario_doc and nome_beneficiario_doc == nome_beneficiario_comp):
                        melhor_correspondencia = comprovante
                        break
                
                # Se não encontrou por CNPJ/CPF/nome, tenta por valor total do reembolso
                if not melhor_correspondencia and valor_total_reembolso_doc:
                    for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in comprovantes:
                        if any(abs(vc - valor_total_reembolso_doc) / valor_total_reembolso_doc <= 0.005 for vc in valores_comp):
                            melhor_correspondencia = comprovante
                            break
                
                # Se não encontrou por valor total, tenta por valores individuais
                if not melhor_correspondencia:
                    for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in comprovantes:
                        if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                            melhor_correspondencia = comprovante
                            break
                
                # Se encontrou correspondência, adiciona ao grupo
                if melhor_correspondencia:
                    agrupados[nome_doc] = [melhor_correspondencia, doc]
                    # Remove o comprovante da lista para evitar duplicação
                    comprovantes.remove((melhor_correspondencia, nome_comp, valores_comp, nome_beneficiario_comp))
    
    # Adiciona comprovantes sem correspondência
    for identificacao, grupo in grupos_identificacao.items():
        for comprovante, nome_comp, valores_comp, nome_beneficiario_comp in grupo["comprovantes"]:
            nome_referencia = f"Sem Correspondência - {nome_comp}"
            agrupados[nome_referencia] = [comprovante]
    
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
            st.write(f"📂 Arquivo gerado: {output_filename}")
    
    return pdf_resultados, zip_path

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    
    # Adicionando um key único ao file_uploader
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True, key="file_uploader")
    
    if arquivos and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs", key="process_button"):
            pdf_resultados, zip_path = organizar_por_cnpj_cpf_e_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(
                        label=f"📄 Baixar {nome}",
                        data=f,
                        file_name=nome,
                        mime="application/pdf",
                        key=f"download_{nome}"  # Adicionando um key único para cada botão de download
                    )
            
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="📥 Baixar todos como ZIP",
                    data=f,
                    file_name="comprovantes_agrupados.zip",
                    mime="application/zip",
                    key="download_zip"  # Adicionando um key único para o botão de download do ZIP
                )

if __name__ == "__main__":
    main()
