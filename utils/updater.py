"""Local test builds are updated using their reviewed installer."""


def run_update(branch='main'):
    raise RuntimeError(
        'Diese lokale Testversion wird über ein neues Installationspaket aktualisiert. '
        'Automatische Git-Resets sind deaktiviert, damit lokale Änderungen erhalten bleiben.')


if __name__ == '__main__':
    run_update()
