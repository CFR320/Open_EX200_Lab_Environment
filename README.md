# Laboratorio de práctica EX200

Laboratorio local para practicar tareas tipo RHCSA sobre AlmaLinux 10. El repositorio incluye una interfaz web, un pool de preguntas tomado del documento de referencia y validaciones de solo lectura ejecutadas por SSH en dos nodos de examen.

## Alcance de esta primera versión

- El documento aporta 20 preguntas principales y 5 adicionales. Cada intento contiene las 20 principales y selecciona 4 de las 5 adicionales al azar; así se conservan las dependencias entre ejercicios (por ejemplo, usuarios, contenedores y LVM).
- Cada pregunta vale 12,5 puntos; la puntuación máxima es 300 y se aprueba desde 210.
- La sesión dura 3 horas. La hora límite se calcula también en el servidor local.
- Las comprobaciones actuales evalúan el estado final de la máquina. Las tareas interactivas de recuperación del arranque se resuelven desde la consola del hipervisor; se comprueba después el estado de la contraseña de root.
- Una tercera VM, `gateway`, proporciona DNS, NTP, NFS, un proxy/caché para los repositorios AlmaLinux 10 y un registro OCI local con la imagen base del ejercicio de contenedores.
- El gateway también sirve los archivos de construcción del ejercicio y ofrece una cuenta `student` para iniciar una sesión SSH interactiva en `node1`.
- Los servicios de dependencias requieren conectividad a Internet durante el aprovisionamiento inicial y para descargar paquetes que no estén en la caché; no es un mirror ISO offline completo.

## Requisitos

- Linux, macOS o Windows con WSL2.
- VirtualBox o VMware Workstation/Fusion.
- Vagrant 2.4.9 o posterior y la caja oficial `almalinux/10`.
- Python 3.9 o posterior, OpenSSH y conectividad para descargar la caja y los paquetes iniciales.
- 8 GB de RAM para las VMs (2 + 3 + 3 GB), además de memoria para el sistema anfitrión, y espacio para tres VMs.

Vagrant necesita el proveedor/plugin correspondiente. La caja oficial `almalinux/10` publica proveedores Hyper-V, VMware y VirtualBox. En Hyper-V, el anfitrión debe tener habilitado el proveedor y el conmutador `Default Switch`. El primer arranque crea también un conmutador interno `ex200-lab` y una segunda interfaz por VM para la red aislada del laboratorio; ejecuta Vagrant con permisos que permitan administrar Hyper-V. La primera ejecución descarga una caja específica de ese proveedor. Para VMware, instala el plugin de proveedor de Vagrant VMware. La configuración de VMware limita el hardware virtual a la versión 19 para mantener compatibilidad con VMware Workstation 16.2.5.

En VirtualBox, el tráfico privado de los nodos usa una red interna aislada del anfitrión; SSH desde el anfitrión sigue disponible mediante los puertos NAT que administra Vagrant. Así se evita depender de los rangos host-only permitidos por la configuración local de VirtualBox.

## Arranque

Desde el directorio del repositorio, elige el proveedor:

```bash
vagrant up --provider=virtualbox
# o: vagrant up --provider=hyperv
```

La primera ejecución descarga AlmaLinux, instala las herramientas usadas por las preguntas y puede tardar varios minutos. En VMware, ejecuta las máquinas una a una para evitar conflictos de bloqueo del provider:

```bash
vagrant up gateway --provider=vmware_desktop
vagrant up node1 --provider=vmware_desktop
vagrant up node2 --provider=vmware_desktop
```

Para desplegar primero la pasarela y ver sus errores por separado:

```bash
vagrant up gateway --provider=virtualbox
vagrant up node1 node2 --provider=virtualbox
```

También se pueden desplegar todas las máquinas con `vagrant up --provider=virtualbox`. Vagrant deja disponibles las conexiones SSH:

```bash
vagrant ssh node1
vagrant ssh node2
```

Si actualizas VMs existentes que ya estaban encendidas, aplica la nueva interfaz con un reinicio normal (no destruye sus discos) y después configura la ruta y el DNS sin reprovisionar sus ejercicios:

```bash
vagrant reload node1 --no-provision
vagrant reload node2 --no-provision
vagrant provision node1 --provision-with lab-network
vagrant provision node2 --provision-with lab-network
```

En un despliegue antiguo, ejecuta también `vagrant provision node1 --provision-with base` una vez para crear la cuenta local `remoteuser6` que corresponde al UID exportado por NFS. No reprovisiones la base de `node2` si quieres conservar el estado de recuperación de root y tuned.

La configuración de ruta y DNS de `lab-network` se reaplica automáticamente en cada `vagrant up` o `vagrant reload`, ya que Vagrant puede restablecer las conexiones de red al arrancar. Si usas `--no-provision`, ejecuta manualmente los dos comandos `vagrant provision ... --provision-with lab-network` anteriores.

Para trabajar desde la pasarela:

```bash
vagrant ssh gateway
sudo -iu student
ssh node1
```

La cuenta de práctica `student` con contraseña inicial `redhat` y acceso SSH por contraseña desde la red privada está habilitada en node1. En node2, `student` permanece bloqueado y no tiene sudo: la recuperación de root debe hacerse desde la consola de la VM, sin saltarse el ejercicio por SSH. El acceso SSH directo de root está deshabilitado; después de recuperar la contraseña, inicia sesión como root en la consola. Para otras tareas de node2, el anfitrión conserva el acceso administrativo mediante Vagrant. Para practicar directamente en node1, entra mediante Vagrant y usa `sudo -iu student`.

Si node1 rechaza la contraseña de `student`, repara ese acceso sin reprovisionar los ejercicios:

```bash
vagrant provision node1 --provision-with lab-access
```

El gateway sirve el archivo de repositorios de ejemplo en `http://content.example.com/repos/ex200.repo`. Los nombres `classroom.example.com`, `content.example.com` y `registry.lab.example.com` solo se resuelven desde la red privada del laboratorio.

La pantalla/consola de cada VM en el hipervisor está disponible para recuperación de GRUB, contraseña o arranque. En node2, el menú de GRUB permanece visible durante 60 segundos para permitir editar la entrada del kernel con `e`; root empieza bloqueado y tuned usa inicialmente el perfil `balanced` para que esas tareas no aparezcan ya resueltas. El segundo disco de 2 GB se asigna a node2 para practicar swap y LVM; el nombre del dispositivo se debe confirmar con `lsblk` porque puede variar por proveedor.

Inicia la API/validador en la máquina anfitriona (Vagrant y el proveedor nunca se ejecutan dentro del contenedor):

```bash
python3 server.py
```

En otra terminal, sirve la interfaz estática en un contenedor Docker o Podman:

```bash
docker compose up -d
# o, sin Compose:
podman run --rm --name ex200-web \
  -p 127.0.0.1:8080:80 \
  -v "$PWD/static:/usr/share/nginx/html:ro,Z" \
  docker.io/library/nginx:stable-alpine
```

Para Docker sin SELinux, elimina el sufijo `,Z` del montaje. Abre <http://127.0.0.1:8080>. La página llama a la API del anfitrión en `http://127.0.0.1:8000`; CORS solo permite los orígenes localhost incluidos en `EX200_ALLOWED_ORIGINS`. No publiques esos puertos en la red: la API puede iniciar Vagrant o destruir las máquinas y no tiene autenticación.

Desde la página puedes elegir el proveedor, desplegar las tres VMs y comenzar cuando estén encendidas. **Restablecer laboratorio** destruye las tres VMs y sus discos y vuelve a desplegar un laboratorio limpio. **Eliminar laboratorio** destruye las VMs y deja el laboratorio apagado y sin desplegar. Ambas acciones eliminan los datos guardados en los discos virtuales; no las uses si necesitas conservarlos. Después de restablecer, inicia el intento manualmente cuando el laboratorio esté listo.

Al finalizar el intento, el servidor se conecta por SSH a cada nodo y ejecuta verificadores locales de solo lectura como root. Si una máquina está apagada o no se puede conectar, la interfaz muestra un error y permite reintentar la corrección. La puntuación no se guarda entre reinicios del servidor.

La interfaz solo contiene HTML, CSS y JavaScript: el contenedor Nginx no recibe sockets, credenciales ni acceso al hipervisor. La API sigue ligada a `127.0.0.1`, donde invoca Vagrant en el anfitrión.

## Contenedores y consolas web

El panel **Consolas de las máquinas** permite incrustar el cliente web configurado o abrirlo en una pestaña aparte. Para VMware, la aplicación configura por defecto una URL noVNC distinta para cada VM en los puertos 6081-6083. Para otros clientes/proveedores puedes definir URL propias; no pongas credenciales en ellas:

```bash
export EX200_CONSOLE_URLS='{
  "virtualbox": {
    "gateway": "http://127.0.0.1:8081/guacamole/",
    "node1": "http://127.0.0.1:8081/guacamole/",
    "node2": "http://127.0.0.1:8081/guacamole/"
  },
  "hyperv": {
    "gateway": "https://wac.example.test",
    "node1": "https://wac.example.test",
    "node2": "https://wac.example.test"
  }
}'
python3 server.py
```

La URL VMware por defecto es `http://127.0.0.1:6081/vnc.html?autoconnect=1` para gateway; node1 y node2 usan 6082 y 6083. Instala el proxy noVNC una sola vez en Windows y arranca la API con `py server.py`; la API inicia y detiene automáticamente los tres proxies:

```powershell
.\scripts\setup_novnc.ps1
py server.py
```

No abras directamente los puertos 5901-5903 en un navegador: son el protocolo VNC, no HTTP. Usa las URL web 6081-6083. `EX200_CONSOLE_URLS`, cuando se define, sustituye el mapa predeterminado. Para VirtualBox/VMware la página intenta incrustar el cliente; si el cliente bloquea la inserción en un marco, usa **Abrir consola web**. Guacamole y noVNC ofrecen controles de teclado según protocolo; esta aplicación no envía pulsaciones por su cuenta.

### VirtualBox

VirtualBox ofrece VRDE/VRDP mediante un Oracle Extension Pack compatible que incluya el módulo VRDE; VRDP habla RDP y puede conectarse a través de Apache Guacamole. Comprueba `VBoxManage list extpacks`; `VRDE Module` debe indicar el módulo. La documentación de [VirtualBox Remote Display](https://www.virtualbox.org/manual/ch07.html#vrde) especifica que está desactivado por defecto.

**Limitación comprobada en VirtualBox 7.2.22:** el Extension Pack oficial 7.2.22 disponible para este host solo declara integración OCI y PXE; no contiene `VBoxVRDP` ni declara `VRDEModule`. El Extension Pack oficial 7.1.10 sí incluye `VBoxVRDP`, pero no se debe instalar sobre VirtualBox 7.2.22: el paquete debe coincidir con la versión del hipervisor. Para usar VRDE en este host habría que cambiar VirtualBox y el Extension Pack a una combinación compatible que incluya ese módulo. Se inspeccionaron los paquetes oficiales sin instalarlos ni aceptar su licencia.

El intento de downgrade en Fedora 45 quedó bloqueado antes de instalar nada: el RPMFusion VirtualBox 7.1.6 para Fedora 42 necesita `libvpx.so.9`, ausente en Fedora 45, que aporta `libvpx.so.12`. No fuerces el paquete ni sustituyas la biblioteca del sistema para salvar esta dependencia; busca una compilación mantenida para la versión exacta de Fedora o usa otro host compatible.

Opta por habilitar la consola antes de iniciar la API:

```bash
export EX200_VBOX_VRDE=1
export EX200_VBOX_VRDE_PASSWORD='una-frase-secreta-de-12-caracteres'
python3 server.py
```

Vagrant asigna los puertos 5101-5103, limita VRDE a `127.0.0.1` y exige autenticación `VBoxAuthSimple` con usuario `ex200`. Puedes cambiar la dirección con `EX200_VBOX_VRDE_ADDRESS`; no la expongas a una red sin reglas de firewall y autenticación fuerte. El Extension Pack puede tener condiciones de licencia distintas a la edición base.

### VMware

El provider de Vagrant permite personalizar claves VMX ([documentación](https://developer.hashicorp.com/vagrant/docs/providers/vmware/configuration#vmx-customization)); VNC es una interfaz VMX específica de VMware, no una API estable de Vagrant. Este laboratorio la habilita automáticamente en cada VM:

| VM | Dirección (solo anfitrión) | Puerto | Contraseña |
|---|---|---:|---|
| gateway | `127.0.0.1` | 5901 | `Ex200Vnc` |
| node1 | `127.0.0.1` | 5902 | `Ex200Vnc` |
| node2 | `127.0.0.1` | 5903 | `Ex200Vnc` |

La contraseña fija de ocho caracteres es solo para este entorno de pruebas. VMware la guarda en texto claro en la configuración VMX: protege `.vagrant` y no cambies la escucha de `127.0.0.1` ni expongas estos puertos en una red no confiable. La contraseña no sustituye la configuración de noVNC/Guacamole necesaria para mostrar la consola dentro del navegador; sin ese proxy, usa un cliente VNC con la dirección, puerto y contraseña de la tabla. El panel de consolas muestra los mismos datos para cada VM.

Al crear una VM con `vagrant up`, VMware inicia VNC junto con la máquina. Para aplicar el cambio a VMs existentes, recárgalas una por una (no destruye sus discos):

```bash
vagrant reload gateway
vagrant reload node1
vagrant reload node2
```

La API publica el cliente web de noVNC en cada puerto indicado; en su barra de herramientas están el teclado virtual y las teclas especiales. Para VirtualBox, configura tres conexiones RDP en Guacamole hacia `127.0.0.1:5101`, `:5102` y `:5103`, usuario `ex200` y la contraseña de VRDE configurada arriba.

Con los valores `127.0.0.1`, los proxies de consola deben correr directamente en el anfitrión. Si los ejecutas en contenedores, necesitarán una dirección del anfitrión alcanzable desde la red del contenedor. Cambiar a `0.0.0.0` facilita esa ruta, pero expone el servicio en todas las interfaces; hazlo solo con contraseña, firewall que limite origen/puerto y una red confiable. La consola web siempre debe quedar protegida por autenticación y publicarse solo en localhost.

### Hyper-V

Hyper-V no expone mediante Vagrant un stream de framebuffer estándar que esta aplicación pueda incrustar en una página. Windows Admin Center ofrece administración web del host y un flujo **Connect** para la VM, pero la documentación de Microsoft indica que la consola usa VMConnect/archivo RDP y un cliente RDP nativo, no una consola de navegador equivalente a Guacamole. El enlace configurado abre WAC; la consola de GRUB/arranque, Ctrl+Alt+Supr y el teclado virtual se manejan desde VMConnect/RDP en el anfitrión. Consulta [Manage Virtual Machines with Windows Admin Center](https://learn.microsoft.com/en-us/windows-server/manage/windows-admin-center/use/manage-virtual-machines).

La consulta de estado de Vagrant puede tardar más en Hyper-V; la API espera hasta 90 segundos, conserva el proveedor detectado si vence el tiempo y reutiliza brevemente el último estado para evitar repetir consultas lentas. Así la sección de consolas sigue visible aunque falle una consulta de estado. La integración de enlaces está disponible para los tres proveedores, pero la consola framebuffer embebida de Hyper-V no es viable de forma portable con la interfaz actual. No se instala XRDP dentro del guest como sustituto: eso mostraría un escritorio invitado separado y no la consola real de arranque/GRUB.

## Gestión de máquinas

El cambio desde la caja Rocky Linux no convierte las VMs existentes: antes de usar AlmaLinux, guarda fuera de las VMs cualquier dato que quieras conservar, destruye las máquinas anteriores y créalas de nuevo con el proveedor elegido.

```bash
vagrant status
vagrant halt
vagrant up
vagrant destroy
```

`vagrant destroy` elimina las máquinas virtuales y sus datos; úsalo solo si quieres reiniciar el laboratorio.

## Estructura

- `data/questions.json`: banco de preguntas y reparto por nodo.
- `checks.py`: verificadores que se ejecutan dentro de las máquinas.
- `server.py`: API local, selección aleatoria, cronómetro de servidor y puntuación.
- `compose.yaml`: contenedor Nginx para publicar únicamente los archivos estáticos de `static/`.
- `static/`: frontend.
- `provision/base.sh`: configuración inicial común de los nodos de examen.
- `provision/lab-interface.sh`: asignación de la dirección fija en la segunda interfaz de red.
- `provision/lab-network.sh`: rutas, DNS y gateway compartidos de los nodos.
- `vagrant/hyperv_network.rb` y `vagrant/hyperv_lab_network.ps1`: conmutador e interfaces adicionales para Hyper-V.
- `gateway/provision.sh`: aprovisionamiento de DNS, NTP, NFS, proxy de repositorios y registro OCI.
- `gateway/containers/`: fuentes del ejercicio de contenedores.
- `RHCSA Exam 20-3-2024 T Translated.docx`: documento fuente.

## Verificación local

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py checks.py
```

## Próximos pasos

1. Completar la validación funcional en VMware; Hyper-V ya se desplegó y pasó pruebas de conectividad, repositorios y servicios básicos.
2. Ajustar tareas y validadores tras completar intentos con esta infraestructura.
3. Completar la infraestructura de las preguntas bloqueadas según `PLAN_PRUEBAS_CORRECCION.md`.

Este laboratorio es un proyecto de práctica comunitario y no está afiliado a Red Hat.
