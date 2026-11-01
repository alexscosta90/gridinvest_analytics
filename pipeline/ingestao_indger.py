from pipeline.db import BASE_DIR
from pipeline.ingestao import ingerir_csv

COLUNAS_INDGER = [
    "DatGeracaoConjuntoDados",
    "NumCNPJ",
    "SigAgente",
    "NomAgente",
    "NomTipoOutorga",
    "DatReferenciaInformada",
    "CodMunicipioIBGE",
    "QtdUCAtiva",
    "QtdUCAtivaFat",
    "QtdFatura",
    "QtdFaturaSemLeitura",
    "QtdFaturaSemLeituraImpAcesso",
    "QtdFaturaSemLeituraEmergencia",
    "QtdFaturaSemLeituraPlurimensa",
    "QtdFaturaSemLeituraFatEstimad",
    "QtdFaturaSemLeituraFimContrat",
    "QtdFaturaSemLeituraAusenciaTm",
    "QtdRefaturamento",
    "QtdFaturaAcerto",
    "QtdFaturaAcertoFatIncorreto",
    "QtdFaturaAcertoFatIncorDevDob",
    "QtdFaturaAcertoFatIncorDevSEC",
    "QtdFaturaAcertoFatIncorDevSET",
    "QtdFaturaAcertoFatImpAcesso",
    "QtdFaturaAcertoFatEmergencia",
    "QtdFaturaSemLeituraFatMedia",
    "QtdFaturaSemLeituraFatCustoDi",
    "QtdFaturaComLeitura",
    "QtdFaturaComAutoleitura",
    "QtdConsComLeituraPlurimensal",
    "QtdConsComAutoleitura",
    "QtdRestAnteDist",
    "QtdRestAtrasadoDist",
    "QtdRestPendenteDist",
    "QtdRestPendenteAtrasado",
    "VlrRestAnte",
    "VlrRestAtrasado",
    "VlrRestPendente",
    "VlrRestPendenteAtrasado",
    "QtdSolicRessarcimentoDano",
    "QtdRessarcIndeferido",
    "VlrPendentePgtRessarcDanoDefe",
    "VlrPagoRessarcDano",
    "QtdUCSubstMedidor",
    "QtdPostoAtendimento",
    "QtdDiasNormal",
    "QtdDiasCasoFortForcMaior",
    "QtdAtendRealizPosto",
    "QtdAtendRealizPostoDiaCasoFor",
    "MdaTempoMedAtendimentoPosto",
    "MdaTempoMedAtendPostoDiaFort",
    "QtdAtendRealizMais30MinDiaNor",
    "QtdAtendRealizMais30MinDiaFor",
    "QtdInspecVerifProcIrregular",
    "QtdTermosOcorrInspecao",
    "QtdTermosOcorrInspecaoCobr",
    "QtdTermosOcorrInspecaoEncerr",
    "QtdProceCobrDefMedidor",
    "QtdReligCobr",
    "QtdUCSuspInadimplemento",
    "QtdSuspIndev",
    "VlrTotCompSuspIndevida",
    "DthCarga",
]


def ingerir_indger():
    """Carrega os dados comerciais do INDGER na camada RAW."""

    caminho = BASE_DIR / "raw" / "indger-dados-comerciais.csv"

    ingerir_csv(
        caminho=caminho,
        tabela="indger_comerciais",
        separador=";",
        colunas_esperadas=COLUNAS_INDGER,
    )


if __name__ == "__main__":
    ingerir_indger()
