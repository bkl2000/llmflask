Du fuehrst einen projektspezifischen Review der bisherigen agentischen
Bearbeitung durch. Zielgruppe sind die Maintainer des Projekts.

## Untersuchungsrahmen

- Lege zuerst den untersuchten Zeitraum, die verfuegbaren Quellen und deren
  Grenzen offen.
- Nutze Repository-Dateien, Git-Historie, Diffs, Tests, CI-Konfiguration,
  Projekt-Trace und vorhandene Sitzungsprotokolle. Behaupte keinen Context
  Loss, wenn keine Sitzungs- oder Projektdokumentation ihn belegt.
- Kennzeichne jeden Befund als `beobachtet`, `dokumentiert` oder `abgeleitet`.
  Nenne mindestens einen konkreten Beleg: Commit, Datei, Test, Tool-Aufruf oder
  protokollierte Entscheidung.
- Bewerte jeden problematischen Befund mit Schweregrad (`hoch`, `mittel`,
  `niedrig`) und Konfidenz (`hoch`, `mittel`, `niedrig`).
- Trenne normale iterative Entwicklung von vermeidbaren Agentenfehlern. Eine
  Folgekorrektur allein beweist weder Context Loss noch mangelnde Kompetenz.

## Prueffelder

1. Context Selection
   Wurden relevante Dateien, Anforderungen, Abhaengigkeiten und bestehende
   Entscheidungen beruecksichtigt? Was fehlte, was war unnoetig?

2. Context Loss und Context Compaction
   Wurden fruehere Anforderungen, Entscheidungen oder Einschraenkungen
   nachweisbar vergessen oder verfaelscht? Welche Befunde sind nur Indizien?

3. Tool Strategy
   Waren Suche, Dateioperationen, Shell-Befehle und Tests zielgerichtet? Nenne
   fehlende oder unnoetige Aufrufe.

4. Agent Loop und Token Overhead
   Gab es belegbare Wiederholungen, planloses Suchen, mehrfaches Lesen oder
   uebergrosse Aenderungsschritte, die Review und Fehlerlokalisierung
   erschwerten?

5. Verification Loop
   Wurden Aenderungen durch passende Unit-, Integrations-, Smoke-, Remote-,
   Syntax-, Lint- oder Typpruefungen abgesichert? Ein gruener Testlauf gilt nur
   fuer die tatsaechlich abgedeckten Risiken.

6. Regression Risk
   Welche bestehenden Funktionen, Daten, Schnittstellen oder Betriebsablaeufe
   konnten oder koennen durch die Aenderungen unbeabsichtigt beschaedigt
   werden?

7. Harness- versus Modellproblem
   Ordne jede wesentliche Schwaeche einer oder mehreren Ursachen zu:
   unzureichende Modellkompetenz, schlechte Kontextauswahl, ungeeignete
   Agentenstrategie, fehlende oder schlechte Tools oder unklare
   Benutzeranforderung.

8. Prompt- und Projektoptimierung
   Schlage konkrete, priorisierte Aenderungen an Prompt, `AGENTS.md`,
   Projektstruktur, Tests, CI oder Arbeitsablauf vor. Vermeide allgemeine
   Lehrbuchratschlaege.

## Ausgabeformat

- Was gut funktioniert hat
- Erkannte Probleme
- Ursache der Probleme
- Konkrete Verbesserungen
- Optimierter Folgeprompt

Beginne mit Untersuchungsrahmen und Evidenzgrenzen. Ordne Probleme nach
Schweregrad und beziehe jede Aussage konkret auf das untersuchte Projekt.
