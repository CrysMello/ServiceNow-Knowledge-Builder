# Acceptance tests

Reserved for end-to-end flows described in SRS Chapter 8 (Casos de Uso):
start a recording, navigate, pause/resume, stop and export, review a
session, recover an interrupted session. These tests exercise the fully
wired CLI (`snkb record`, via `typer.testing.CliRunner`) backed by a
real `ApplicationControllerPort` built from `snkb.bootstrap.create_controller`,
and therefore require every module (Chapters 3-10 of the Module
Specifications) to be implemented first.
