# Laboratorio de práctica EX200

Laboratorio local para practicar tareas tipo RHCSA sobre Rocky Linux 10. El repositorio incluye una interfaz web, un pool de preguntas tomado del documento de referencia y validaciones de solo lectura ejecutadas por SSH en dos nodos de examen.

## Alcance de esta primera versión

- El documento aporta 20 preguntas principales y 5 adicionales. Cada intento contiene las 20 principales y selecciona 4 de las 5 adicionales al azar; así se conservan las dependencias entre ejercicios (por ejemplo, usuarios, contenedores y LVM).
- Cada pregunta vale 12,5 puntos; la puntuación máxima es 300 y se aprueba desde 210.
- La sesión dura 3 horas. La hora límite se calcula también en el servidor local.
- Las comprobaciones actuales evalúan el estado final de la máquina. Las tareas interactivas de recuperación del arranque se resuelven desde la consola del hipervisor; se comprueba después el estado de la contraseña de root.
- Una tercera VM, `gateway`, proporciona DNS, NTP, NFS, un proxy/caché para los repositorios Rocky Linux 10 y un registro OCI local con la imagen base del ejercicio de contenedores.
- El gateway también sirve los archivos de construcción del ejercicio y ofrece una cuenta `student` para iniciar una sesión SSH interactiva en `node1`.
- Los servicios de dependencias requieren conectividad a Internet durante el aprovisionamiento inicial y para descargar paquetes que no estén en la caché; no es un mirror ISO offline completo.

## Requisitos

- Linux, macOS o Windows con WSL2.
- VirtualBox, VMware Workstation/Fusion o Hyper-V.
- Vagrant 2.4.9 o posterior y la caja `rockylinux/10`.
- Python 3.9 o posterior, OpenSSH y conectividad para descargar la caja y los paquetes iniciales.
- 8 GB de RAM para las VMs (2 + 3 + 3 GB), además de memoria para el sistema anfitrión, y espacio para tres VMs.

Vagrant necesita el proveedor/plugin correspondiente. En Hyper-V, crea o selecciona el conmutador virtual que Vagrant solicite. Para VMware, instala el plugin de proveedor de Vagrant VMware. La caja oficial Rocky Linux 10 probada publica proveedores VirtualBox, VMware y libvirt, pero no Hyper-V; este proveedor necesita una caja Rocky compatible distinta.

En VirtualBox, el tráfico privado de los nodos usa una red interna aislada del anfitrión; SSH desde el anfitrión sigue disponible mediante los puertos NAT que administra Vagrant. Así se evita depender de los rangos host-only permitidos por la configuración local de VirtualBox.

La metadata de la caja `rockylinux/10` puede apuntar a artefactos antiguos ya retirados. Si la descarga automática falla con HTTP 404, consulta el directorio oficial de imágenes Rocky y añade la caja del proveedor elegido localmente (`vagrant box add --name rockylinux/10 --provider virtualbox <URL>`); verifica el checksum SHA-256 oficial antes de instalarla.

## Arranque

Desde el directorio del repositorio, elige el proveedor:

```bash
vagrant up --provider=virtualbox
# o: vagrant up --provider=vmware_desktop
# o: vagrant up --provider=hyperv
```

La primera ejecución descarga Rocky Linux, instala las herramientas usadas por las preguntas y puede tardar varios minutos. Para desplegar primero la pasarela y ver sus errores por separado:

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

Inicia la interfaz y el validador en la máquina anfitriona:

```bash
python3 server.py
```

Abre <http://127.0.0.1:8000>. Mantén el servidor ligado a localhost: la aplicación usa la configuración SSH de Vagrant y no implementa autenticación para acceso desde una red.

Al finalizar el intento, el servidor se conecta por SSH a cada nodo y ejecuta verificadores locales de solo lectura como root. Si una máquina está apagada o no se puede conectar, la interfaz muestra un error y permite reintentar la corrección. La puntuación no se guarda entre reinicios del servidor.

## Gestión de máquinas

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
- `static/`: frontend.
- `provision/base.sh`: configuración inicial común de los nodos de examen.
- `provision/lab-network.sh`: rutas, DNS y gateway compartidos de los nodos.
- `gateway/provision.sh`: aprovisionamiento de DNS, NTP, NFS, proxy de repositorios y registro OCI.
- `gateway/containers/`: fuentes del ejercicio de contenedores.
- `RHCSA Exam 20-3-2024 T Translated.docx`: documento fuente.

## Verificación local

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py checks.py
```

## Próximos pasos

1. Validar el aprovisionamiento y los ejercicios de servicios compartidos en VMware y Hyper-V; las pruebas previas se han realizado con VirtualBox.
2. Ajustar tareas y validadores tras completar intentos con esta infraestructura.
3. Completar la infraestructura de las preguntas bloqueadas según `PLAN_PRUEBAS_CORRECCION.md`.

Este laboratorio es un proyecto de práctica comunitario y no está afiliado a Red Hat.
