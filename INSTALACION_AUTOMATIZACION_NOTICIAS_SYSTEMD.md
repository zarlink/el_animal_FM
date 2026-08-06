# Instalación de la descarga automática de noticias con systemd

Esta guía explica cómo registrar `12_automatizar_descarga_noticias.py` como un servicio de usuario de `systemd`, ejecutarlo al iniciar el equipo y programarlo todos los días a las 12:00 y 21:30.

La configuración está preparada para Linux con `systemd`. No corresponde a Windows ni a distribuciones que utilicen otro gestor de servicios.

## 1. Configuración utilizada actualmente

En el equipo actual se utilizan estos valores:

```text
Usuario: zlnk
Proyecto: /home/zlnk/PycharmProjects/el_animal_FM
Python: /home/zlnk/PycharmProjects/el_animal_FM/env_animal/bin/python
Coordinador: /home/zlnk/PycharmProjects/el_animal_FM/12_automatizar_descarga_noticias.py
Servicios de usuario: /home/zlnk/.config/systemd/user
Zona horaria: America/Santiago
```

Al instalarlo en otro equipo hay que reemplazar `zlnk` y las rutas anteriores por el usuario y la ubicación real del proyecto.

## 2. Requisitos previos

Comprobar que el sistema utiliza `systemd`:

```bash
systemctl --version
```

Comprobar que existen el coordinador y el intérprete del entorno virtual:

```bash
test -f /home/zlnk/PycharmProjects/el_animal_FM/12_automatizar_descarga_noticias.py && echo "Coordinador encontrado"
test -x /home/zlnk/PycharmProjects/el_animal_FM/env_animal/bin/python && echo "Python encontrado"
```

Verificar que el coordinador se puede cargar:

```bash
cd /home/zlnk/PycharmProjects/el_animal_FM
env_animal/bin/python -m py_compile 12_automatizar_descarga_noticias.py
```

Probar el cálculo de fechas sin descargar noticias ni modificar el estado:

```bash
env_animal/bin/python 12_automatizar_descarga_noticias.py --dry-run
```

También se debe comprobar que el sistema tenga configurada la zona horaria de Chile:

```bash
timedatectl
```

El resultado debe indicar:

```text
Time zone: America/Santiago
```

Si el equipo utiliza otra zona horaria, se puede establecer con:

```bash
sudo timedatectl set-timezone America/Santiago
```

Este cambio afecta la zona horaria de todo el equipo.

## 3. Crear el directorio de servicios del usuario

La carpeta puede no existir en una instalación nueva. Se crea con:

```bash
mkdir -p ~/.config/systemd/user
```

Los archivos se instalarán allí porque la descarga debe ejecutarse con el usuario normal y no como `root`.

## 4. Crear el servicio

Crear el archivo:

```bash
nano ~/.config/systemd/user/el-animal-noticias.service
```

Agregar este contenido:

```ini
[Unit]
Description=Descarga automática de noticias El Animal FM
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/zlnk/PycharmProjects/el_animal_FM
Environment="PYTHONPATH=/home/zlnk/PycharmProjects/el_animal_FM/src"
Environment="PYTHONUNBUFFERED=1"
Environment="TZ=America/Santiago"
ExecStart=/home/zlnk/PycharmProjects/el_animal_FM/env_animal/bin/python /home/zlnk/PycharmProjects/el_animal_FM/12_automatizar_descarga_noticias.py
```

En `nano`, guardar con `Ctrl+O`, confirmar con `Enter` y salir con `Ctrl+X`.

`Type=oneshot` significa que el servicio se inicia, ejecuta las descargas y termina. Por eso puede aparecer posteriormente como `inactive (dead)` aunque haya finalizado correctamente.

No es necesario ejecutar `source env_animal/bin/activate`: `ExecStart` llama directamente al intérprete del entorno virtual.

## 5. Crear el temporizador

Crear el archivo:

```bash
nano ~/.config/systemd/user/el-animal-noticias.timer
```

Agregar este contenido:

```ini
[Unit]
Description=Programación automática de noticias El Animal FM

[Timer]
OnStartupSec=2min
OnCalendar=*-*-* 12:00:00
OnCalendar=*-*-* 21:30:00
Persistent=true
Unit=el-animal-noticias.service

[Install]
WantedBy=timers.target
```

Esta configuración produce tres comportamientos:

1. Ejecuta una comprobación dos minutos después de iniciar el gestor de servicios del usuario.
2. Ejecuta el servicio todos los días a las 12:00.
3. Ejecuta el servicio todos los días a las 21:30.

`Persistent=true` permite recuperar una activación programada que se perdió mientras el computador estaba apagado. El coordinador calcula además los días pendientes utilizando su archivo de estado.

## 6. Validar los archivos

Antes de habilitarlos, revisar ambas unidades:

```bash
systemd-analyze --user verify \
  ~/.config/systemd/user/el-animal-noticias.service \
  ~/.config/systemd/user/el-animal-noticias.timer
```

Si no aparecen errores, recargar las unidades:

```bash
systemctl --user daemon-reload
```

Es importante incluir `--user` en todos los comandos relacionados con estas unidades. Sin esa opción, `systemctl` buscará un servicio global en `/etc/systemd/system` y responderá que la unidad no existe.

## 7. Probar manualmente el servicio

Iniciar una descarga manual:

```bash
systemctl --user start el-animal-noticias.service
```

La orden puede tardar mientras se descargan las noticias. Después, revisar el resultado sin truncar las líneas:

```bash
systemctl --user status el-animal-noticias.service --no-pager --full
```

Revisar los registros completos:

```bash
journalctl --user -u el-animal-noticias.service --since "10 minutes ago" --no-pager -o cat
```

Una ejecución correcta termina con código `0/SUCCESS`. Que el servicio quede como `inactive (dead)` es normal para una unidad `oneshot`.

## 8. Habilitar el temporizador

Habilitarlo para futuras sesiones e iniciarlo inmediatamente:

```bash
systemctl --user enable --now el-animal-noticias.timer
```

Comprobar que esté habilitado:

```bash
systemctl --user is-enabled el-animal-noticias.timer
```

Resultado esperado:

```text
enabled
```

Comprobar que esté activo:

```bash
systemctl --user is-active el-animal-noticias.timer
```

Resultado esperado:

```text
active
```

Consultar la siguiente ejecución:

```bash
systemctl --user list-timers --all el-animal-noticias.timer
```

El estado detallado del temporizador debe mostrar `active (waiting)`:

```bash
systemctl --user status el-animal-noticias.timer --no-pager --full
```

## 9. Ejecutar aunque el usuario no inicie sesión

Un servicio de usuario normalmente comienza cuando el usuario inicia sesión. Para iniciar su gestor de servicios durante el arranque del equipo, incluso sin abrir una sesión gráfica, habilitar `linger`:

```bash
sudo loginctl enable-linger zlnk
```

En otro computador se debe sustituir `zlnk` por el nombre del usuario correspondiente.

Comprobarlo con:

```bash
loginctl show-user zlnk -p Linger
```

Resultado esperado:

```text
Linger=yes
```

Con el temporizador habilitado y `Linger=yes`, el gestor de servicios del usuario se inicia durante el arranque y `OnStartupSec=2min` activa la descarga aproximadamente dos minutos después.

## 10. Validación final

Ejecutar las siguientes comprobaciones:

```bash
systemctl --user is-enabled el-animal-noticias.timer
systemctl --user is-active el-animal-noticias.timer
loginctl show-user zlnk -p Linger
systemctl --user list-timers --all el-animal-noticias.timer
```

La configuración está completa cuando se obtiene:

```text
Temporizador habilitado: enabled
Temporizador activo: active
Inicio sin sesión: Linger=yes
Próxima ejecución: 12:00 o 21:30, según corresponda
```

Después de reiniciar el equipo se puede confirmar la ejecución de arranque con:

```bash
journalctl --user -u el-animal-noticias.service -b --no-pager
```

## 11. Administración habitual

Ejecutar una descarga manual:

```bash
systemctl --user start el-animal-noticias.service
```

Detener temporalmente la programación:

```bash
systemctl --user stop el-animal-noticias.timer
```

Volver a iniciar la programación:

```bash
systemctl --user start el-animal-noticias.timer
```

Deshabilitar y detener el temporizador:

```bash
systemctl --user disable --now el-animal-noticias.timer
```

Revisar las ejecuciones del día:

```bash
journalctl --user -u el-animal-noticias.service --since today --no-pager
```

Consultar la última y la próxima activación:

```bash
systemctl --user show el-animal-noticias.timer \
  -p LastTriggerUSec \
  -p NextElapseUSecRealtime
```

## 12. Solución de problemas

### `Unit el-animal-noticias.service not found`

Comprobar que se está usando `--user`:

```bash
systemctl --user start el-animal-noticias.service
```

Después de crear o modificar una unidad siempre se debe ejecutar:

```bash
systemctl --user daemon-reload
```

### Python indica que no encuentra el coordinador

Verificar el nombre y la ruta configurados en `ExecStart`:

```bash
systemctl --user cat el-animal-noticias.service
ls -l /home/zlnk/PycharmProjects/el_animal_FM/12_automatizar_descarga_noticias.py
```

El nombre debe ser exactamente `12_automatizar_descarga_noticias.py`.

Después de corregir el servicio:

```bash
systemctl --user daemon-reload
systemctl --user reset-failed el-animal-noticias.service
systemctl --user start el-animal-noticias.service
```

### La salida de `status` aparece cortada

Usar:

```bash
systemctl --user status el-animal-noticias.service --no-pager --full
```

Si se abrió el paginador y aparece `(END)`, salir presionando `q`.

### El temporizador no funciona antes de iniciar sesión

Comprobar `linger`:

```bash
loginctl show-user zlnk -p Linger
```

Si responde `Linger=no`, habilitarlo:

```bash
sudo loginctl enable-linger zlnk
```

### Consultar el error real del servicio

```bash
journalctl --user -u el-animal-noticias.service -n 100 --no-pager -o cat
```

## 13. Resumen de archivos instalados

```text
Proyecto:
/home/zlnk/PycharmProjects/el_animal_FM/12_automatizar_descarga_noticias.py

Servicio:
/home/zlnk/.config/systemd/user/el-animal-noticias.service

Temporizador:
/home/zlnk/.config/systemd/user/el-animal-noticias.timer

Estado generado por el coordinador:
/home/zlnk/PycharmProjects/el_animal_FM/automation/news_download_state.json
```

El archivo de bloqueo se crea automáticamente durante las ejecuciones para impedir que dos descargas se ejecuten al mismo tiempo.
