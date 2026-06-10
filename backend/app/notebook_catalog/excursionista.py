"""Caderno Excursionista — 31 requisitos."""

from app.notebook_catalog.builders import opt_req, req, sec

EXCURSIONISTA = {
    "slug": "excursionista",
    "name": "Excursionista",
    "min_age": 14,
    "advanced_title": "Excursionista na Mata",
    "color_hex": "#6366f1",
    "sections": [
        sec("I", "Gerais", [
            req(1, "Ter, no mínimo, quatorze anos de idade."),
            req(2, "Ser membro ativo do Clube de Desbravadores."),
            req(3, "Memorizar e explicar o significado do Objetivo JA."),
            req(4, "Ler livro do Clube de Leitura Juvenil e resumir em uma página."),
            req(5, 'Ler o livro "O Fim do Começo".'),
        ]),
        sec("II", "Descoberta Espiritual", [
            req(1, "Memorizar 12 Apóstolos e Frutos do Espírito."),
            req(2, "Ler versos e leitura bíblica",
                 "Versos: Rom. 8:28; Apoc. 21:1-3; II Ped. 1:20-21; I João 2:14; II Cro. 20:20; Salmo 46.\n"
                 "Leitura: Mateus 24–28; Marcos; Lucas; João; Atos 1–8 (cartão)."),
        ]),
        sec("III", "Servindo a Outros", [
            req(1, "Relacionamento adventista no dia a dia",
                 "Discutir conduta com vizinhos, escola, atividades sociais e recreativas."),
        ]),
        sec("IV", "Desenvolvendo Amizade", [
            req(1, "Avaliação em dois temas",
                 "Autoestima, relacionamento familiar, finanças pessoais ou pressão de grupo."),
        ]),
        sec("V", "Saúde e Aptidão Física", [
            req(1, "Lista de atividades inclusivas e organizar uma delas."),
            req(2, "Completar especialidade de Temperança."),
        ]),
        sec("VI", "Organização e Liderança", [
            req(1, "Organograma da igreja local e funções dos departamentos."),
            req(2, "Participar de dois programas com diferentes departamentos."),
            req(3, "Completar especialidade Aventuras com Cristo."),
        ]),
        sec("VII", "Estudo da Natureza", [
            req(1, "Nicodemos e ciclo da borboleta com significado espiritual."),
            req(2, "Especialidade de Estudos da Natureza não realizada anteriormente."),
        ]),
        sec("VIII", "Arte de Acampar", [
            req(1, "Trilha de 20 km com pernoite e relatório de flora/fauna."),
            req(2, "Completar especialidade de Pioneirias."),
        ]),
        sec("IX", "Estilo de Vida", [
            opt_req(1, "Especialidade (escolha de área)",
                     "Missionárias; Agrícolas; Ciência e Saúde; Habilidades Domésticas.",
                     "excursionista_ix_esp"),
        ]),
        sec("AV", "Classe Avançada — Excursionista na Mata", [
            opt_req(1, "Conversa em unidade sobre tema",
                     "Modéstia cristã, recreação, saúde ou observância do sábado.",
                     "excursionista_av_tema"),
            req(2, "Especialidade de Ordem Unida (se não realizada)."),
        ], advanced=True),
    ],
}
