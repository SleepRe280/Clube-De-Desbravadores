"""Caderno Companheiro — 37 requisitos."""

from app.notebook_catalog.builders import opt_req, req, sec

COMPANHEIRO = {
    "slug": "companheiro",
    "name": "Companheiro",
    "min_age": 11,
    "advanced_title": "Companheiro de Excursionismo",
    "color_hex": "#22c55e",
    "sections": [
        sec("I", "Gerais", [
            req(1, "Ter, no mínimo, onze anos de idade."),
            req(2, "Ser membro ativo do Clube de Desbravadores."),
            req(3, "Ilustrar de forma criativa o significado do Voto dos Desbravadores."),
            req(4, "Ler o livro do Clube de Leitura Juvenil do ano e escrever parágrafo sobre o livro."),
            req(5, 'Ler o livro "Um simples lanche".'),
            req(6, "Participar ativamente da classe bíblica do seu clube."),
        ]),
        sec("II", "Descoberta Espiritual", [
            req(1, "Memorizar 10 Mandamentos e 27 livros do Novo Testamento",
                "Demonstrar habilidade para encontrar qualquer livro do NT na Bíblia."),
            req(2, "Ler e explicar versos e leitura bíblica",
                "Versos: Isa. 41:9-10; Heb. 13:5; Prov. 22:6; I João 1:9; Salmo 8.\n"
                "Leitura: Levítico 11; Números; Deuteronômio; Josué; Juízes; Rute; 1 e 2 Samuel (capítulos do cartão)."),
            req(3, "Tema bíblico escolhido com conselheiro",
                "Escolher parábola, milagre, Sermão da Montanha ou Segunda Vinda; demonstrar por troca de ideias, "
                "atividade em grupo ou redação."),
        ]),
        sec("III", "Servindo a Outros", [
            req(1, "Duas horas de serviço comunitário prático com companheirismo."),
            req(2, "Cinco horas em projeto que beneficie comunidade ou igreja."),
        ]),
        sec("IV", "Desenvolvendo Amizade", [
            req(1, "Respeito a culturas, raças e sexo",
                "Conversar com conselheiro ou unidade sobre respeito a pessoas de diferentes culturas, raça e sexo."),
        ]),
        sec("V", "Saúde e Aptidão Física", [
            opt_req(1, "Especialidade (escolha única)",
                     "Natação Principiante II ou Acampamento II.", "companheiro_v_esp"),
        ]),
        sec("VI", "Organização e Liderança", [
            req(1, "Dirigir ou colaborar em meditação criativa para unidade ou clube."),
            req(2, "Ajudar a planejar excursão ou acampamento com pelo menos um pernoite."),
        ]),
        sec("VII", "Estudo da Natureza", [
            req(1, "Especialidade de natureza não realizada anteriormente."),
        ]),
        sec("VIII", "Arte de Acampar", [
            req(1, "Habilidades de acampamento e primeiros socorros básicos."),
        ]),
        sec("IX", "Estilo de Vida", [
            req(1, "Especialidade em Artes e Habilidades Manuais não realizada anteriormente."),
        ]),
        sec("AV", "Classe Avançada — Companheiro de Excursionismo", [
            opt_req(1, "Atividade sobre saúde (escolha única)",
                     "Curso antitabagismo; dois filmes sobre saúde; cartaz sobre drogas; "
                     "exposição/passeata; pesquisa e página sobre saúde.", "companheiro_av_saude"),
            opt_req(2, "Cerimônia do clube (escolha única)",
                     "Participar e sugerir ideias para Investidura, Admissão de lenço ou Dia do Desbravador.",
                     "companheiro_av_cerimonia"),
            opt_req(3, "Especialidade avançada (escolha única)",
                     "Habilidades Domésticas; Ciência e Saúde; Atividades Missionárias; Atividades Agrícolas.",
                     "companheiro_av_esp"),
        ], advanced=True),
    ],
}
