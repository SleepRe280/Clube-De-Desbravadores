"""Caderno Pioneiro — 35 requisitos."""

from app.notebook_catalog.builders import opt_req, req, sec

PIONEIRO = {
    "slug": "pioneiro",
    "name": "Pioneiro",
    "min_age": 13,
    "advanced_title": "Pioneiro de Novas Fronteiras",
    "color_hex": "#f97316",
    "sections": [
        sec("I", "Gerais", [
            req(1, "Ter, no mínimo, treze anos de idade."),
            req(2, "Ser membro ativo do Clube de Desbravadores."),
            req(3, "Memorizar e entender o Alvo e o Lema JA."),
            req(4, "Ler livro do Clube de Leitura Juvenil e resumir em uma página."),
            req(5, 'Ler o livro "Expedição Galápagos".'),
        ]),
        sec("II", "Descoberta Espiritual", [
            req(1, "Memorizar as Bem-Aventuranças (Sermão da Montanha)."),
            req(2, "Ler versos e leitura bíblica",
                 "Versos: Isa. 26:3; Rom. 12:12; João 14:1-3; Sal. 37:5; Filip. 3:12-14; Salmo 23; I Sam. 15:22.\n"
                 "Leitura: Eclesiastes; Isaías; Jeremias; Daniel; profetas menores; Mateus 1–23 (cartão)."),
            req(3, "Conversar sobre cristianismo e discipulado",
                 "O que é cristianismo; características do verdadeiro discípulo; como ser cristão verdadeiro."),
        ]),
        sec("III", "Servindo a Outros", [
            req(1, "Participar de dois projetos missionários do clube."),
            req(2, "Trabalhar em projeto comunitário da igreja, escola ou comunidade."),
        ]),
        sec("IV", "Desenvolvendo Amizade", [
            req(1, "Debate e avaliação pessoal em dois temas",
                 "Autoestima, amizade, relacionamentos ou otimismo/pessimismo."),
        ]),
        sec("V", "Saúde e Aptidão Física", [
            req(1, "Programa pessoal de exercícios com compromisso assinado."),
            req(2, "Discutir vantagens do estilo de vida adventista segundo a Bíblia."),
        ]),
        sec("VI", "Organização e Liderança", [
            opt_req(1, "Seminário ou treinamento",
                     "Ministério Pessoal ou Evangelismo oferecido pela igreja/distrito.",
                     "pioneiro_vi_seminario"),
        ]),
        sec("VII", "Estudo da Natureza", [
            req(1, "Participar de atividade social da igreja."),
            req(2, "Estudar dilúvio e fossilização."),
            req(3, "Especialidade em Estudos da Natureza não realizada anteriormente."),
        ]),
        sec("VIII", "Arte de Acampar", [
            req(1, "Fazer fogo refletor e demonstrar uso."),
            req(2, "Acampamento de fim de semana com mochila adequada."),
            req(3, "Completar especialidade de Resgate básico."),
        ]),
        sec("IX", "Estilo de Vida", [
            opt_req(1, "Especialidade (escolha de área)",
                     "Atividades Missionárias, Profissionais ou Agrícolas — nova.",
                     "pioneiro_ix_esp"),
        ]),
        sec("AV", "Classe Avançada — Pioneiro de Novas Fronteiras", [
            opt_req(1, "Atividade física com relatório (2+ páginas)",
                     "Caminhar 10 km; cavalgar 2 km; canoa 2h; ciclismo 15 km; natação 200 m; "
                     "corrida 1500 m; patins 2 km.", "pioneiro_av_atividade"),
            opt_req(2, "Item de comunicação ou natureza",
                     "10 plantas comestíveis; semáforo 35 letras/min; código náutico; "
                     "Mateus 24 em LIBRAS; Salmo 23 em Braile.", "pioneiro_av_item2"),
            opt_req(3, "Coleção identificada",
                     "25 folhas, 25 rochas/minerais, 25 flores, 25 borboletas ou 25 conchas.",
                     "pioneiro_av_colecao"),
        ], advanced=True),
    ],
}
