# Plan de pruebas de corrección EX200

## Alcance y entorno probado

- Intento aleatorio: `tIT8YXqK-ytdYh47hsr4UdrMAoV-gT5u`.
- 24 preguntas: las 20 principales y las adicionales 1-4; la adicional 5 no fue seleccionada.
- Rocky Linux 10.2, VirtualBox 7.2.22, Vagrant 2.4.9; `node1` y `node2`.
- Se resolvieron los ejercicios mediante SSH y se ejecutó el conjunto real de validadores por SSH como root.
- Resultado automatizado: **237,5/300 (19/24; aprobado, umbral 210)**.
- Se reiniciaron ambas VMs y se repitieron los validadores; puntuación y tareas persistentes sin cambios.
- Después, la API creó y corrigió un segundo intento aleatorio (`5FNAv9zX63SmubTNMdMycm9GifSIIhuA`): **225/300 (18/24; aprobado)**. Incluyó ACL, que no se había preparado en el primer intento.
- La infraestructura compartida se desplegó después en `gateway` sin destruir los discos de los nodos. Para VirtualBox se usa una red interna aislada porque el host no permite la subred del laboratorio en modo host-only.
- Smoke tests del gateway: servicios persistentes tras reinicio, DNS y rutas en ambos nodos, metadatos XML BaseOS/AppStream por el proxy, autenticación del registro, build rootless como `student`, PDF generado por el worker, NFSv4 del home de UID 2006 y respuesta NTP desde `classroom.example.com`.
- Estos smoke tests comprueban las dependencias, no resuelven las preguntas en la cuenta `student` ni sustituyen un intento completo de examen con el nuevo gateway.

## Resultado por pregunta

| Pregunta | Nodo | Criterio principal | Resultado |
|---:|:---:|---|---|
| 1 | node1 | IP, ruta y DNS persistentes del enunciado | La red interna `172.25.250.0/24`, gateway `.254` y DNS `.254.254` ya están desplegados; el script `lab-network` configura ambos nodos sin quitar la NIC NAT de Vagrant. |
| 2 | node1 | BaseOS y AppStream habilitados | El proxy local devuelve metadatos XML válidos de Rocky Linux 10 en las dos URL del enunciado. Falta resolver la pregunta desde `student`. |
| 3 | node1 | HTTP en puerto 82, SELinux, firewall y arranque | Superada; `curl` devolvió HTTP 200 tras reiniciar. Se corrigió el validador para reconocer la lista de puertos de `semanage`. |
| 4 | node1 | Dos entradas cron de natasha | Superada; ambas entradas persistieron tras reiniciar. |
| 5 | node1 | sysadms, natasha, harry y sarah/nologin | Superada. |
| 6 | node1 | `/home/sysadms`, grupo, 2770 y SGID | Superada. |
| 7 | node1 | chronyd usando classroom.example.com | El DNS del gateway resuelve el nombre y NTP responde desde `.250.254`; se verificó con una fuente temporal de chrony. El corrector identifica la fuente por IP porque la búsqueda inversa la presenta como `_gateway`. Falta la configuración persistente del ejercicio. |
| 8 | node1 | Automontaje NFS de remoteuser6 | NFSv4 montó `classroom.example.com:/home/remoteuser6`; el archivo de prueba fue legible como UID 2006. Falta configurar autofs como pide el ejercicio. |
| 9 | node1 | bob con UID 2112 | Superada. |
| 10 | node1 | `/root/test.tar.gz` contiene `/var/tmp` | Superada; el archivo se pudo listar con `tar -tzf`. |
| 11 | node1 | Archivos de sarah bajo `/root/find_user` | Superada. |
| 12 | node1 | Líneas con `home` en `/root/search.txt` | Superada. |
| 13 | node1 | Imagen `monitor` | Se validó login y build rootless con `student`; la imagen se eliminó al terminar para no dejar la pregunta resuelta. |
| 14 | node1 | Contenedor asciipdf y servicio de usuario | Se validó que el worker genera un PDF. La unidad systemd de usuario y su persistencia tras reiniciar siguen pendientes. |
| 15 | node2 | root tiene contraseña utilizable | Estado final superado por el validador. **No se probó la recuperación interactiva desde GRUB/consola**; se habilitó root por SSH administrativo para completar el estado. Requiere una prueba manual específica. |
| 16 | node2 | BaseOS y AppStream habilitados | Las mismas URL locales y metadatos BaseOS/AppStream están disponibles en node2; falta configurar los repositorios desde `student`. |
| 17 | node2 | Swap de 512 MiB activa y persistente | Superada tras reiniciar. Se ajustó el umbral del validador por los 4 KiB que `mkswap` reserva en una partición nominal de 512 MiB. |
| 18 | node2 | lvname ext3, montado en `/mnt/lvname` | Superada tras reiniciar. Se creó en `groupname` con 50 extensiones de 8 MiB. |
| 19 | node2 | lvname entre 200 y 300 MiB | Superada; FS y LV reducidos de forma segura fuera de línea a 232 MiB. |
| 20 | node2 | Perfil tuned recomendado y habilitado | Superada; `virtual-guest` quedó activo tras reiniciar. |
| Adicional 1 | node1 | Script mysearch y copia a `/root/myfiles` | Superada; se interpretó el tamaño como 10 MiB o más, según el enunciado presentado. |
| Adicional 2 | node1 | Caducidad máxima de 30 días | Superada para cuentas del laboratorio. Se excluyó `vagrant` (cuenta técnica SSH) para evitar bloquear el corrector; su contraseña había quedado expirada y fue restaurada offline. |
| Adicional 3 | node1 | Mensaje al iniciar sesión harry | Superada. |
| Adicional 4 | node1 | Grupo elite con sudo sin contraseña | Superada; `visudo -c` validó la configuración. |
| Adicional 5 | node1 | ACL en `/var/tmp/fstab` | No seleccionada en este intento. |

Las cinco preguntas con cero puntos en esta ejecución fueron 1, 7, 8, 13 y 14. Las de repositorio se calificaron usando mirrors Rocky oficiales como sustitución; el documento fuente aporta enlaces RHEL de ejemplo que no sirven para Rocky 10 y omite los enlaces de node2.

## Pruebas de corrección automatizada

| ID | Prueba | Criterio de aceptación | Resultado actual |
|---|---|---|---|
| API-01 | Crear intento nuevo | 24 preguntas únicas, 20 principales + 4 adicionales, 300 puntos totales | Aprobada en pruebas de API/unitarias |
| API-02 | Corregir intento contra dos VMs encendidas | Respuesta con 24 detalles y puntuación entre 0 y 300 | Aprobada para este intento |
| API-03 | Salidas de shell 0 y no-cero | Código 0 cuenta correcto; cualquier otro código cuenta incorrecto sin abortar la corrección | Aprobada; regresión añadida |
| VM-01 | SSH y sudo no interactivo en ambos nodos | `vagrant ssh` y `sudo -n` disponibles; ambos nodos alcanzan la red interna y el gateway | Aprobada |
| VM-02 | Reinicio | Servicios, usuarios, repositorios, swap y montaje sobreviven al reinicio | Aprobada para los elementos seleccionados que son configurables |
| CHECK-01 | SELinux/HTTP | Puerto TCP 82 permitido por SELinux/firewalld y respuesta HTTP válida | Aprobada |
| CHECK-02 | NFS | Acceso al home produce un montaje NFS real | NFSv4 y permisos UID 2006 aprobados; autofs del examen pendiente |
| CHECK-03 | Chrony | Fuente classroom resuelta y visible en `chronyc sources -n` | DNS y respuesta NTP aprobados; configuración persistente y prueba del corrector pendientes |
| CHECK-04 | Contenedores | Imagen, unidad systemd de usuario y persistencia tras reinicio | Login, build rootless y PDF aprobados; unidad systemd de usuario pendiente |
| CHECK-05 | Recuperación de root | Recuperar desde la consola del hipervisor y confirmar el inicio local de root; SSH de student/root no está habilitado en node2 | Pendiente de comprobación manual |

## Verificación posterior de aprovisionamiento (2026-11-05)

- En Linux con Vagrant 2.4.9 y VirtualBox, `vagrant validate` pasó y las tres máquinas arrancaron sin reprovisionar las bases de los nodos.
- El aprovisionamiento del gateway encontró primero una dirección DNS IPv6 que nginx rechazaba en la directiva `resolver`. Ahora el proxy selecciona un resolver IPv4; el aprovisionamiento completo pasó.
- `lab-network` no encontraba la NIC NAT si la ruta por defecto inicial estaba en la interfaz del laboratorio. Ahora identifica la otra conexión activa y configura correctamente ambos nodos.
- `lab-network` se ejecuta en cada `vagrant up` y `vagrant reload`, porque Vagrant puede restablecer las conexiones de red al reconfigurar las NIC. Se comprobó con recargas normales de ambos nodos sin reprovisionar `base`.
- En node2, el menú de GRUB se mantiene visible 60 segundos para editar la entrada del kernel durante la recuperación de root. La configuración generada pasó `grub2-script-check` y persistió tras una recarga normal; los seis validadores de node2 siguieron aprobados.
- Para preservar Q15, `student` está bloqueado y sin sudo en node2; el SSH desde gateway como `student` y el SSH directo como root se rechazan. El acceso administrativo por Vagrant sigue disponible para aprovisionamiento y corrección. Tras aplicar esta política, node2 mantuvo sus seis validadores aprobados sin cambiar el estado de la contraseña de root.
- Después de las recargas, pasaron DNS para `classroom.example.com` y `registry.lab.example.com`, el health endpoint del gateway, los metadatos BaseOS/AppStream, y el automontaje NFS. Los validadores dieron 15/19 en node1 y 6/6 en node2; las fallas restantes corresponden a Chrony, los ejercicios de contenedor y ACL aún no resueltos.
- VMware y Hyper-V siguen pendientes: esta verificación solo pudo ejecutarse con VirtualBox en Linux.

## Acciones para desbloquear y completar

1. Resolver Q7, Q13 y Q14 desde `student`, sin reutilizar las acciones de smoke test como respuestas del usuario; completar también la adicional 5 cuando sea seleccionada.
2. Ejecutar una prueba manual de Q15 desde la consola de VirtualBox: recuperar GRUB, cambiar la contraseña, completar relabel SELinux y confirmar el inicio de sesión.
3. Repetir un intento completo con gateway, medir la puntuación y reiniciar los nodos para verificar persistencia.
4. Repetir la validación de aprovisionamiento en VMware y Hyper-V cuando esos proveedores estén disponibles.

No ejecutar `vagrant destroy` sobre estas VMs: contienen el estado resuelto de esta ejecución.

## Simulación de despliegue VirtualBox (2026-11-08)

- Entorno: Linux, VirtualBox 7.2.22, Vagrant 2.4.9, 4 CPU y 19 GiB de RAM. Vagrant descargó `almalinux/10` versión `10.2.20260914`; no fue necesario modificar la caja.
- `vagrant up gateway --provider=virtualbox` terminó correctamente. Durante el arranque SSH registró varios `Connection reset`/desconexiones y reintentó hasta que la VM estuvo disponible. El aprovisionador completó; `dnsmasq`, `chronyd`, `nfs-server`, `nginx` y `ex200-registry` quedaron activos, `/health` devolvió `ok` y las exportaciones NFS estuvieron presentes.
- Primer `vagrant up node1 node2 --provider=virtualbox`: `node1` terminó su aprovisionamiento. `node2` arrancó, pero el aprovisionador `base` falló tras agotar los reintentos para obtener el mirrorlist AppStream de AlmaLinux (curl 28/timeout). El diagnóstico mostró que su ruta por defecto inicial era `172.25.250.1` por la NIC interna, que no ofrece salida; la ruta NAT quedaba con menor prioridad. Desde esa ruta, la petición HTTPS al mirror expiró.
- **Corrección aplicada:** se adelantó el provisionador `lab-network` respecto de `base` en `Vagrantfile`. Así la VM establece primero la ruta por `172.25.250.254` y el DNS del gateway, antes de que `dnf` descargue paquetes. Aplicar `lab-network` a `node2` cambió la ruta y la petición HTTPS al mirror pasó a devolver HTTP 200. Después, `vagrant provision node2` completó `base`, `lab-access` y `grub-recovery` sin destruir ni recrear la VM.
- Verificación final: `vagrant validate` pasó; las tres VMs están `running`. En el gateway, los servicios y `/health` respondieron correctamente y `sudo exportfs -s` mostró ambas exportaciones. En ambos nodos, `chronyd`, `crond`, `firewalld` y `tuned` están activos; la consulta HTTP a `content.example.com/health` devolvió `ok`.
- Avisos no bloqueantes: Vagrant reasignó automáticamente los puertos SSH del anfitrión a 2200/2201; `ALREADY_ENABLED: ssh` fue idempotente. El primer `exportfs -s` de verificación se ejecutó sin privilegios y devolvió permiso denegado; repetirlo con `sudo` confirmó las exportaciones activas.
- `PYTHONPATH=. python3 tests/test_server.py`: 15 pruebas aprobadas. `python3 -m py_compile server.py tests/test_server.py`, `ruby -c Vagrantfile` y `git diff --check` pasaron.
- Esta ejecución valida aprovisionamiento e infraestructura básica, no completa un intento de examen ni verifica consolas RDP/VNC. El Extension Pack presente en este host no dispone del módulo VRDE; VMware y Hyper-V no están disponibles para pruebas reales en este host Linux. Las tres VMs se dejaron encendidas.

## Prueba de interfaz y consolas (2026-11-08)

- Se levantaron temporalmente la API local y el contenedor Nginx de `compose.yaml`. El navegador cargó la interfaz, el estado del API mostró las tres máquinas `running` y listas para empezar, y las tarjetas de consola se generaron según proveedor. Una petición desde `http://127.0.0.1:8080` al API en `:8000` respondió HTTP 200 con `Access-Control-Allow-Origin` esperado.
- Se probó el control **Ver en esta página**: la aplicación creó el `iframe` con el URL configurado. No pudo cargar una consola real; el navegador recibió `ERR_CONNECTION_REFUSED` en `127.0.0.1:6082`. No había listeners en 5101-5103 (VRDE/RDP), 5901-5903 (VNC) ni 6081-6083 (noVNC). Las VMs tenían `vrde="off"`.
- **Extension Pack 7.2.22:** el archivo oficial [Oracle_VirtualBox_Extension_Pack-7.2.22-175245.vbox-extpack](https://download.virtualbox.org/virtualbox/7.2.22/Oracle_VirtualBox_Extension_Pack-7.2.22-175245.vbox-extpack) existe y su SHA-256 oficial (`cd5fb32cac59157dc361c90be68ccef1404831aac48ec8377569620afbc9d207`) coincide. Su `ExtPack.xml` no declara `VRDEModule`; solo describe integración OCI y PXE. El pack instalado localmente coincide en versión, descripción y módulos, y `VBoxManage list extpacks` deja `VRDE Module` vacío.
- La documentación oficial [Remote Display (VRDE)](https://www.virtualbox.org/manual/ch07.html#vrde) describe el soporte RDP de VirtualBox, pero los artefactos oficiales 7.2.22 descargados y verificados no contienen el módulo VRDE descrito en la documentación.
- **Pack que sí contiene VRDE:** inspeccioné el paquete Oracle 7.1.10 [Oracle_VirtualBox_Extension_Pack-7.1.10-169112.vbox-extpack](https://download.virtualbox.org/virtualbox/7.1.10/Oracle_VirtualBox_Extension_Pack-7.1.10-169112.vbox-extpack). Su checksum oficial verificado fue `e020755711849fa0ee23d3bc47bc90cb0ea595da7dda804499568a0dc2387989`; el manifiesto declara `<VRDEModule>VBoxVRDP</VRDEModule>` y contiene `linux.amd64/VBoxVRDP.so`. El paquete oficial 7.0.26 inspeccionado también contiene ese módulo. Son versiones incompatibles con el VirtualBox 7.2.22 del host; no instalé ni intenté cargar un pack de otra versión.
- El sitio de Oracle indica que Extension Pack se rige por su licencia PUEL, distinta de la licencia de VirtualBox base. No se aceptó una licencia ni se realizó ninguna instalación o downgrade.
- **VNC VMware:** no fue posible probar una sesión real porque las VMs y el proveedor activos son VirtualBox. La UI admite enlaces de noVNC, pero este host no tiene noVNC/websockify ni un servidor VNC corriendo. El teclado virtual y Ctrl+Alt+Supr tampoco se pudieron validar contra una consola remota real.
- Se ajustó el texto de ayuda de VirtualBox en la interfaz para exigir un Extension Pack compatible que realmente incluya VRDE, en vez de sugerir que cualquier Oracle Extension Pack lo proporciona.

## Evaluación del downgrade de VirtualBox (2026-11-08)

- Host Fedora 45 Workstation, VirtualBox/RPMFusion `7.2.22-1.fc45`, kernel `7.2.15-300.fc45`; las tres VMs seguían encendidas. No había una versión anterior instalada ni disponible en los repositorios configurados. Se dejaron encendidas durante la evaluación.
- Encontré paquetes RPMFusion 7.1.6 para Fedora 42 y verifiqué que el Extension Pack oficial 7.1.6 sí contiene `VBoxVRDP`. Su checksum oficial coincidió; el manifiesto declara `VRDEModule=VBoxVRDP`.
- Simulé la transacción DNF con los paquetes RPMFusion 7.1.6 para Fedora 42, sin aplicar cambios. DNF la rechazó porque `VirtualBox-server` requiere `libvpx.so.9`, no disponible en Fedora 45. El host tiene `libvpx` 1.17 con ABI `.so.12`; no sustituí ni forcé esa biblioteca, porque podría romper aplicaciones multimedia instaladas.
- Resultado: **no se realizó el downgrade ni se instaló el Extension Pack**. Las VMs, discos, paquetes y kernel actual permanecen sin cambios. No es seguro usar el paquete RPMFusion de Fedora 42 ni instalar módulos del Extension Pack 7.1.6 en la versión 7.2.22. Para continuar hace falta una compilación 7.1.x compatible con Fedora 45 y sus bibliotecas, o realizar el cambio en otro host soportado y con respaldo integral.

## Problema despliegue en VMWare

- La operación falló: Vagrant terminó con código 1. 
```gateway: Copying config sha256:67fd5f7b4b120eaa3308775fe87aff98a2492287576bd6656ef785d54a1b5605 gateway: Writing manifest to image destination gateway: 67fd5f7b4b120eaa3308775fe87aff98a2492287576bd6656ef785d54a1b5605 gateway: 819a3608182f70da6f3a62786802855ddd8c4cac120be867774f07d527dab06f gateway: Created symlink '/etc/systemd/system/multi-user.target.wants/ex200-registry.service' → '/etc/systemd/system/ex200-registry.service'. gateway: Error: get credentials: reading JSON file "/run/ex200-registry-auth.OB0GnB": unmarshaling JSON at "/run/ex200-registry-auth.OB0GnB": unexpected end of JSON input The SSH command responded with a non-zero exit status. Vagrant assumes that this means the command failed. The output for this command should be in the log above. Please read the output to determine what went wrong.```
- **Causa:** `mktemp` crea el authfile vacío; `podman login` intenta leerlo como JSON antes de guardar las credenciales y falla con `unexpected end of JSON input`.
- **Corrección aplicada:** inicializar el authfile temporal con el JSON válido `{"auths":{}}` antes de ejecutar `podman login`. Verificado abajo con el aprovisionamiento real del gateway.
- **Error posterior en node1:** el `ping` de node1 a `172.25.250.254` funcionaba, pero `/health` devolvía HTTP 404. En el gateway faltaba `/var/www/ex200/health`, que se crea al final del script; por tanto, la VM seguía parcialmente aprovisionada y el error del nodo era una consecuencia, no un fallo de la red VMware.
- **Recuperación verificada:** `vagrant provision gateway` completó el inicio de sesión y push al registro (`Login Succeeded`). Después, `/health` devolvió `ok` desde gateway y node1; `vagrant up node1 --provider=vmware_desktop` aplicó `lab-network` y terminó correctamente. `vagrant up node2 --provider=vmware_desktop` también terminó correctamente. Las tres VMs quedaron en ejecución, sin destruir ni recrear las existentes.
- **Prevención:** en despliegues VMware la aplicación comprueba la salud local del gateway antes de arrancar los nodos y, solo si falla, ejecuta `vagrant provision gateway` y vuelve a comprobarla. Se añadió una prueba de regresión para la recuperación de un gateway que devuelve 404.
