<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Subphora en tu mini PC: guía paso a paso

Al terminar tendrás Subphora funcionando en un mini PC de tu casa, con candado (HTTPS),
contraseña para cada persona de la familia, una copia de seguridad cada noche y la app
instalada en el móvil. Cuenta con una tarde la primera vez.

Los comandos van en recuadros: cópialos tal cual. Donde pone `<algo>` cambia eso por lo tuyo.

## 1. Lo que necesitas

- **Un mini PC** con procesador Intel o AMD (por ejemplo un Intel N100), 8 GB de RAM o más
  y un disco SSD de 256 GB o más. Un ARM (Raspberry Pi 5 con 8 GB) también vale.
- **Un disco USB** para las copias de seguridad (otro disco, no el del mini PC).
- **Acceso a tu router** (la contraseña de administración, suele estar en una pegatina).
- **Tu ordenador Windows**, solo para preparar el mini PC y escribirle comandos. No se
  instala nada en él salvo el programa para crear el USB de instalación.

## 2. Instalar Ubuntu Server en el mini PC

1. En Windows, descarga **Ubuntu Server 26.04 LTS** de ubuntu.com/download/server y
   **Rufus** de rufus.ie. Con Rufus graba la imagen en un pendrive.
2. Arranca el mini PC desde el pendrive (tecla F7, F11 o F12 al encender, según la marca)
   y sigue el instalador: idioma, teclado español, disco entero, tu nombre de usuario y
   contraseña. **Marca "Install OpenSSH server"**. No marques nada más.
3. Al acabar, quita el pendrive y reinicia. La pantalla mostrará la dirección del mini PC
   en tu red, algo como `192.168.1.50`. Apúntala.

Desde ahora trabajas desde Windows. Abre **PowerShell** y conéctate:

```
ssh <tu-usuario>@192.168.1.50
```

Pon tu contraseña (no se ve al escribir). Todo lo que sigue se escribe ahí.

## 3. Preparar el mini PC

Actualizaciones automáticas de seguridad, Docker y la herramienta de GitHub:

```
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y unattended-upgrades gh git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Sal (`exit`) y vuelve a entrar con `ssh` para que el último cambio cuente. Comprueba:

```
docker run --rm hello-world
```

## 4. Que tu casa se pueda encontrar desde fuera

El móvil, en el campo, tiene que llegar a tu mini PC. Hacen falta tres cosas.

**a) Que tu conexión tenga dirección pública propia.** Mira la dirección de Internet del
router (en su página, apartado "WAN" o "Internet") y compárala con la que da
`curl ifconfig.me` en el mini PC. Si **no coinciden**, o la del router empieza por `100.`,
tu compañía te tiene detrás de un "CGNAT". Llama y pide "salir del CGNAT" o "una IP
pública": muchas lo hacen gratis. Sin eso, lo demás no funcionará.

**b) Un nombre.** Gratis con DuckDNS:

1. Entra en duckdns.org con tu cuenta de Google o GitHub.
2. Escribe un nombre (por ejemplo `pozo-familia`) y pulsa "add domain". Tu dirección será
   `pozo-familia.duckdns.org`.
3. Copia el **token** que aparece arriba. Es una contraseña: no lo compartas.

(Si prefieres un dominio propio, unos 10 € al año, crea un registro A que apunte a tu
dirección pública y salta la parte de DuckDNS.)

**c) Abrir el router hacia el mini PC.** En la página del router:

1. **IP fija para el mini PC** (a veces se llama "reserva DHCP" o "IP estática"): reserva
   la `192.168.1.50` para él.
2. **Redirige puertos** ("port forwarding", "NAT" o "servidores virtuales") a
   `192.168.1.50`: el **80 TCP**, el **443 TCP** y el **443 UDP**. Ningún otro.

## 5. El disco de las copias

Conecta el disco USB y busca su nombre (el que tenga el tamaño de tu disco, p. ej. `sdb1`):

```
lsblk -o NAME,SIZE,LABEL,FSTYPE
```

Si es nuevo y vacío, dale formato (**borra todo lo que tenga**):

```
sudo mkfs.ext4 -L copias /dev/<sdb1>
```

Haz que se monte solo al arrancar, en `/mnt/copias`:

```
sudo mkdir -p /mnt/copias
echo "LABEL=copias /mnt/copias ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
sudo mount -a
sudo chown $USER: /mnt/copias
```

## 6. Descargar y configurar Subphora

```
gh auth login
gh repo clone Almoon-D/Subphora ~/Subphora
cd ~/Subphora
mkdir -p data
cp deploy/.env.example deploy/.env
nano deploy/.env
```

En `deploy/.env` rellena (guarda con Ctrl+O, Intro, y sal con Ctrl+X):

- `SUBPHORA_DOMAIN=pozo-familia.duckdns.org`
- `SUBPHORA_BACKUP_DIR=/mnt/copias`
- `DUCKDNS_SUBDOMAIN=pozo-familia` y `DUCKDNS_TOKEN=` el token de DuckDNS.
- `SUBPHORA_UID` y `SUBPHORA_GID`: los números que da `id -u` y `id -g` (casi siempre 1000).
- `AEMET_API_KEY`: déjalo vacío si no tienes clave.

Ese archivo es tuyo: nunca se sube a GitHub.

**Tus datos de piezometría.** Desde PowerShell en Windows (no en el `ssh`), copia la carpeta
que tienes descargada:

```
scp -r C:\ruta\a\piezometry <tu-usuario>@192.168.1.50:~/Subphora/data/
```

## 7. Arrancar

```
cd ~/Subphora/deploy
docker compose --profile duckdns up -d --build
```

La primera vez tarda unos 10 minutos (prepara todo). Después, comprueba:

```
docker compose ps
```

`api` debe decir `healthy`, y `web`, `backup` y `duckdns` `Up`. Abre en el navegador
`https://pozo-familia.duckdns.org`: verás el candado y la pantalla de entrada. Si no hay
candado al principio, espera un minuto: Caddy está pidiendo el certificado.

## 8. Las personas que pueden entrar

Una por persona; te pide la contraseña dos veces (10 caracteres o más):

```
docker compose exec api subphora users add <nombre>
```

Otros: `subphora users list`, `subphora users password <nombre>` (cambia la contraseña y
cierra sus sesiones), `subphora users remove <nombre>`. Siempre precedidos de
`docker compose exec api`. Tras 5 contraseñas fallidas seguidas, ese nombre espera 15
minutos.

## 9. Preparar los mapas

Esto ya lo conoces de las sesiones anteriores; ahora se ejecuta dentro del servidor:

```
docker compose exec api subphora piezometry import
docker compose exec api subphora national build --region <ES-CM>
```

El mapa nacional entero (`--all`) tarda horas: lánzalo por la noche.

## 10. Instalar la app en el móvil

- **Android (Chrome):** abre `https://pozo-familia.duckdns.org`, entra con tu nombre y
  contraseña, toca el menú ⋮ y elige **"Instalar aplicación"** (o "Añadir a pantalla de
  inicio").
- **iPhone (Safari):** abre la dirección, entra, toca el botón **Compartir** (el cuadrado
  con la flecha) y **"Añadir a pantalla de inicio"**.

Aparece el icono de Subphora. La sesión dura 90 días; después pide la contraseña otra vez.
Si caduca estando sin cobertura, lo apuntado en el campo se queda en el móvil y se envía
cuando vuelvas a entrar: no se pierde nada.

Si en casa, con el wifi, no abre pero con datos móviles sí, tu router no sabe "volver a
entrar" en tu propia casa: usa los datos móviles en casa o activa en el router la opción
"NAT loopback" ("hairpin NAT"), si la tiene.

## 11. Copias de seguridad

Cada noche a las 03:30 se guarda una copia de `data/` en el disco USB, se comprueba
leyéndola entera y se borran las que pasen de 14. Lo que se descarga solo (la caché) no se
copia. Para ver cómo van:

```
docker compose logs --tail 20 backup
ls /mnt/copias
```

Una copia a mano: `docker compose exec backup subphora backup create`.

**Recuperar una copia** (por ejemplo, tras un error o en un mini PC nuevo):

```
cd ~/Subphora/deploy
docker compose stop api backup
docker compose run --rm --no-deps backup subphora backup restore /app/backups/<subphora-AAAAMMDD….tar.gz>
docker compose up -d
```

Antes de recuperar, la copia se comprueba entera; si está dañada no toca nada. Lo que había
no se borra: queda en `data/.before-restore-<fecha>`. Cuando veas que todo está bien,
puedes borrar esa carpeta.

Una copia en casa no te salva de un incendio o un robo: de vez en cuando, copia el último
archivo de `/mnt/copias` a otro sitio (un pendrive que guardes fuera, por ejemplo).

## 12. Actualizar Subphora

Cuando haya una versión nueva:

```
cd ~/Subphora
git pull
cd deploy
docker compose --profile duckdns up -d --build
```

Los móviles reciben la versión nueva solos la próxima vez que abran la app con cobertura.

## 13. Si algo falla

- **Ver qué pasa:** `docker compose logs --tail 50 api` (o `web`, `backup`, `duckdns`).
- **No hay candado / "no se puede conectar":** comprueba que `duckdns` dice "updated" en sus
  registros, que los puertos 80 y 443 van al mini PC y que no estás detrás de CGNAT
  (paso 4).
- **Se fue la luz:** no hagas nada; al volver, todo arranca solo.
- **Apagar todo:** `docker compose --profile duckdns down` (los datos se quedan).

## 14. Seguridad, en corto

- Solo los puertos 80 y 443 están abiertos a Internet; `ssh` solo desde tu casa.
- Las contraseñas se guardan cifradas (nadie puede leerlas, ni tú); la sesión va en una
  cookie que solo viaja por HTTPS.
- Tus datos, claves y copias nunca salen del mini PC ni se suben a GitHub.

## 15. Tu ordenador Windows

No queda nada instalado por Subphora. Puedes desinstalar Rufus y borrar la imagen de Ubuntu
cuando el mini PC funcione.
