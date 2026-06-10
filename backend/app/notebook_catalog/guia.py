"""Caderno Guia — 27 requisitos."""

from app.notebook_catalog.builders import opt_req, req, sec

GUIA = {
    "slug": "guia",
    "name": "Guia",
    "min_age": 15,
    "advanced_title": "Guia de Exploração",
    "color_hex": "#f9bc15",
    "sections": [
        sec("I", "Gerais", [
            req(1, "Ter, no mínimo, quinze anos de idade."),
            req(2, "Ser membro ativo do clube de Desbravadores."),
            req(3, "Memorizar e explicar o Voto de Fidelidade à Bíblia."),
            req(4, "Ler livro do Clube de Leitura Juvenil e resumir em uma página."),
            req(5, 'Ler o livro "O livro amargo".'),
        ]),
        sec("II", "Descoberta Espiritual", [
            req(1, "Memorizar 3 Mensagens Angélicas, 7 Igrejas e Pedras Preciosas."),
            req(2, "Ler versos e leitura bíblica",
                 "Versos: I Cor. 13; II Cron. 7:14; Apoc. 22:18-20; II Tim. 4:6-7; Rom. 8:38-39; Mt 6:33-34.\n"
                 "Leitura: Atos; Romanos; cartas paulinas; Hebreus; Tiago; Pedro; João; Apocalipse (cartão)."),
        ]),
        sec("III", "Servindo a Outros", [
            opt_req(1, "Atividade de serviço (escolha única)",
                     "Visita a doente; adotar família necessitada; projeto aprovado pelo líder.",
                     "guia_iii_servico"),
        ]),
        sec("IV", "Desenvolvendo Amizade", [
            req(1, "Palestra e reflexão em dois temas",
                 "Escolha profissional; relacionamento com pais; namoro; plano de Deus para o sexo."),
        ]),
        sec("V", "Saúde e Aptidão Física", [
            opt_req(1, "Atividade de saúde (escolha única)",
                     "Poesia/artigo para publicação; corrida com treinamento; leitura Temperança (p.102-125); "
                     "Nutrição ou liderar Cultura física.", "guia_v_saude"),
        ]),
        sec("VI", "Organização e Liderança", [
            opt_req(1, "Participação em liderança",
                     "Curso para conselheiros; convenção de liderança; duas reuniões de diretoria.",
                     "guia_vi_lideranca"),
        ]),
        sec("VII", "Estudo da Natureza", [
            opt_req(1, "Especialidade (escolha única)",
                     "Ecologia ou Conservação Ambiental.", "guia_vii_esp"),
        ]),
        sec("VIII", "Arte de Acampar", [
            opt_req(1, "Especialidade para mestrado",
                     "Aquática, Esportes, Atividades Recreativas ou Vida Campestre — nova.",
                     "guia_viii_mestrado"),
        ]),
        sec("IX", "Estilo de Vida", [
            opt_req(1, "Especialidade (escolha de área)",
                     "Agrícolas; Ciência e Saúde; Habilidades Domésticas; Profissionais.",
                     "guia_ix_esp"),
        ]),
        sec("AV", "Classe Avançada — Guia de Exploração", [
            opt_req(1, "Evangelismo jovem",
                     "Trazer dois amigos a duas reuniões OU quatro domingos de série evangelística.",
                     "guia_av_evangelismo"),
            req(2, "Relatório sobre trabalho dos diáconos (2 meses)",
                 "Cuidado do templo; lava-pés; batismo; dízimos e ofertas."),
            req(3, "Seminário ou palestra em dois temas",
                 "Aborto, bullying, violência, drogas ou DSTs."),
        ], advanced=True),
    ],
}
