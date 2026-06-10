"""Caderno Pesquisador — 35 requisitos."""

from app.notebook_catalog.builders import opt_req, req, sec

PESQUISADOR = {
    "slug": "pesquisador",
    "name": "Pesquisador",
    "min_age": 12,
    "advanced_title": "Pesquisador de Campo e Bosque",
    "color_hex": "#8b5cf6",
    "sections": [
        sec("I", "Gerais", [
            opt_req(1, "Demonstrar compreensão da Lei do Desbravador",
                     "Por representação, debate ou redação.", "pesquisador_i_lei"),
        ]),
        sec("II", "Descoberta Espiritual", [
            req(1, "Levítico 11 — alimentos comestíveis e não comestíveis."),
            req(2, "Ler versos e leitura bíblica",
                 "Versos: Ecl. 12:13-14; Rom. 6:23; Apoc. 1:3; Isa. 43:1-2; Salmos 51:10 e 16.\n"
                 "Leitura: 1 e 2 Reis; 2 Crônicas; Esdras; Neemias; Ester; Jó; Salmos; Provérbios; Eclesiastes (cartão)."),
            req(3, "História sobre salvação em Jesus",
                 "Escolher Nicodemos, samaritana, bom samaritano, filho pródigo ou Zaqueu; "
                 "demonstrar em grupo, mensagem, cartazes/maquete ou poesia/hino."),
        ]),
        sec("III", "Servindo a Outros", [
            req(1, "Participar de projeto comunitário da cidade com unidade ou clube."),
            req(2, "Participar de três atividades missionárias da igreja."),
        ]),
        sec("IV", "Desenvolvendo Amizade", [
            req(1, "Debate ou representação sobre pressão de grupo."),
            req(2, "Visitar órgão público e descobrir como o clube pode ajudar a comunidade."),
        ]),
        sec("V", "Saúde e Aptidão Física", [
            opt_req(1, "Estilo de vida livre do álcool",
                     "Discussão em classe ou vídeo sobre álcool/drogas com texto pessoal.",
                     "pesquisador_v_alcool"),
        ]),
        sec("VI", "Organização e Liderança", [
            req(1, "Dirigir cerimônia de abertura semanal ou programa de Escola Sabatina."),
            req(2, "Ajudar a organizar a classe bíblica do clube."),
        ]),
        sec("VII", "Estudo da Natureza", [
            req(1, "Especialidade de Estudos da Natureza não realizada anteriormente."),
        ]),
        sec("VIII", "Arte de Acampar", [
            req(1, "Completar especialidades Acampamento III e Primeiros Socorros — básico."),
        ]),
        sec("IX", "Estilo de Vida", [
            req(1, "Usar bússola ou GPS e encontrar endereços em zona urbana."),
            req(2, "Especialidade em Artes e Habilidades Manuais não realizada anteriormente."),
        ]),
        sec("AV", "Classe Avançada — Pesquisador de Campo e Bosque", [
            opt_req(1, "Convidar pessoa a programa da igreja",
                     "Clube, classe bíblica ou pequeno grupo.", "pesquisador_av_convite"),
            opt_req(2, "Especialidade (escolha única)",
                     "Asseio e Cortesia Cristã ou Vida Familiar.", "pesquisador_av_esp1"),
            opt_req(3, "Organizar evento especial do clube",
                     "Investidura, Admissão de Lenço ou Dia do Desbravador.", "pesquisador_av_evento"),
            req(4, "Comunicação alternativa",
                 "Enviar e receber mensagem por semáforos, Morse, LIBRAS ou Braile."),
            opt_req(5, "Duas especialidades (escolha de área)",
                     "Habilidades Domésticas; Ciência e Saúde; Missionárias; Agrícolas — duas novas.",
                     "pesquisador_av_esp2"),
        ], advanced=True),
    ],
}
