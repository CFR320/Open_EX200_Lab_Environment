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
| CHECK-05 | Recuperación de root | Recuperar desde la consola del hipervisor y volver a iniciar por SSH | Pendiente de comprobación manual |

## Verificación posterior de aprovisionamiento (2026-11-05)

- En Linux con Vagrant 2.4.9 y VirtualBox, `vagrant validate` pasó y las tres máquinas arrancaron sin reprovisionar las bases de los nodos.
- El aprovisionamiento del gateway encontró primero una dirección DNS IPv6 que nginx rechazaba en la directiva `resolver`. Ahora el proxy selecciona un resolver IPv4; el aprovisionamiento completo pasó.
- `lab-network` no encontraba la NIC NAT si la ruta por defecto inicial estaba en la interfaz del laboratorio. Ahora identifica la otra conexión activa y configura correctamente ambos nodos.
- `lab-network` se ejecuta en cada `vagrant up` y `vagrant reload`, porque Vagrant puede restablecer las conexiones de red al reconfigurar las NIC. Se comprobó con recargas normales de ambos nodos sin reprovisionar `base`.
- En node2, el menú de GRUB se mantiene visible 60 segundos para editar la entrada del kernel durante la recuperación de root. La configuración generada pasó `grub2-script-check` y persistió tras una recarga normal; los seis validadores de node2 siguieron aprobados.
- Después de las recargas, pasaron DNS para `classroom.example.com` y `registry.lab.example.com`, el health endpoint del gateway, los metadatos BaseOS/AppStream, y el automontaje NFS. Los validadores dieron 15/19 en node1 y 6/6 en node2; las fallas restantes corresponden a Chrony, los ejercicios de contenedor y ACL aún no resueltos.
- VMware y Hyper-V siguen pendientes: esta verificación solo pudo ejecutarse con VirtualBox en Linux.

## Acciones para desbloquear y completar

1. Resolver Q7, Q13 y Q14 desde `student`, sin reutilizar las acciones de smoke test como respuestas del usuario; completar también la adicional 5 cuando sea seleccionada.
2. Ejecutar una prueba manual de Q15 desde la consola de VirtualBox: recuperar GRUB, cambiar la contraseña, completar relabel SELinux y confirmar el inicio de sesión.
3. Repetir un intento completo con gateway, medir la puntuación y reiniciar los nodos para verificar persistencia.
4. Repetir la validación de aprovisionamiento en VMware y Hyper-V cuando esos proveedores estén disponibles.

No ejecutar `vagrant destroy` sobre estas VMs: contienen el estado resuelto de esta ejecución.
