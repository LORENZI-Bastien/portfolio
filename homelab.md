# Homelab : source de vérité

Ce fichier alimente la section « Homelab » du site (`index.html#homelab`) et du profil GitHub.
Une tâche planifiée le relit chaque jour à 5 h et met à jour les deux si quelque chose a changé.

**Règles :** rien de sensible ici (pas d'IP, de nom de domaine, de nom de machine, de compte, d'identifiant ni de nombre d'entrées). Ce fichier n'est pas servi par le site (`_redirects`).

*Dernière mise à jour : 7 novembre 2026*

## En bref
Homelab sur du matériel de récupération : une tour Windows qui fait tourner 14 conteneurs Docker sous WSL2, et un Raspberry Pi 5 allumé 24 h/24. Accès à distance uniquement par Tailscale, aucun port ouvert sur la box, tous les services en HTTPS.

## Machines
| Machine | Matériel | Système | Services |
|---|---|---|---|
| Tour | Ryzen 5 1600, 16 Go, GTX 1660 Super 6 Go, SSD système + disques de données | Windows 10, WSL2, Docker Desktop | Ollama (IA locale sur GPU), Open WebUI, Immich, Jellyfin, Navidrome, Home Assistant, n8n, Uptime Kuma, Homepage (Vaultwarden, Radicale et AdGuard Home restent en place le temps de la bascule vers le Pi) |
| Raspberry Pi 5 | 8 Go, SSD NVMe 256 Go | Raspberry Pi OS 64 bits, Docker | Tailscale, AdGuard Home (DNS de tout le VPN, résolveur amont en DoH), Vaultwarden, Radicale, Immich (migrés depuis la tour), point politique quotidien |

Préparés mais éteints : Prometheus, Grafana, Paperless-ngx.

## Projet maison : point politique quotidien
Petit service en Python (sans dépendance), dans un conteneur Docker sur le Pi, sans aucun port ouvert. Chaque matin, il lit les données ouvertes officielles (scrutins de l'Assemblée nationale, scrutins et textes du Sénat, Panorama des lois de vie-publique) et envoie un résumé neutre sur un salon Discord : votes importants adoptés ou rejetés, détail par groupe politique masqué, et fichier joint avec le vote nominatif des députés et sénateurs. Anti-doublon par fichier d'état, tolérance aux pannes d'une source, 10 tests unitaires. Résumé de contexte par l'IA locale prévu en option.

## Réseau
- Un seul réseau local derrière la box, pas de VLAN
- Tailscale (WireGuard) relie toutes les machines et les téléphones, à la maison comme en 4G
- MagicDNS, `tailscale serve` comme reverse proxy HTTPS, certificats Let's Encrypt
- AdGuard Home sur le Pi sert de DNS filtrant à tout le VPN, avec un plan de repli si le Pi tombe

## Sécurité
- Aucun service exposé sur Internet, aucune redirection de port
- Ports des conteneurs liés à la machine locale uniquement
- Pare-feu sur chaque hôte, activé avec un retour arrière automatique
- SSH par clé, mises à jour de sécurité automatiques
- Secrets dans des fichiers à accès restreint, jamais dans le code
- Inscriptions fermées sur le gestionnaire de mots de passe
- Accès Gmail prévu en lecture seule pour l'IA (prudence face à l'injection de prompt)

## Sauvegardes
- Choix : sauvegardes versionnées sur un disque séparé (rsync avec instantanés datés + dumps cohérents des bases) plutôt qu'un RAID, qui recopie aussi les erreurs
- Script prêt, mais le disque de sauvegarde s'est révélé défaillant : **pas encore de sauvegarde automatique valide**, c'est le point faible actuel
- En attendant : export chiffré du coffre de mots de passe hors de la tour, photos présentes sur la tour et sur le Pi

## Problèmes résolus
- Deux machines invisibles sur le VPN : connectées avec deux comptes différents
- Données « perdues » au redémarrage : Docker démarrait avant WSL, script de démarrage qui attend
- Disque de sauvegarde défaillant : diagnostic par les journaux et `chkdsk` en lecture seule
- Migration de services vers le Pi : export des bases, transfert chiffré, SHA256, comparaison des comptages
- IA dans 6 Go de VRAM : modèles 4-8 B, un seul chargé à la fois
- Reverse proxy refusé par Home Assistant : déclarer le proxy de confiance
- Mots de passe d'admin perdus : réinitialisation sans perte de données, après sauvegarde des bases

## Ce que j'ai appris
WSL2, Docker Compose (volumes, bind mounts, profils, limites mémoire), Tailscale et WireGuard, reverse proxy et TLS, DNS filtrant et DoH, pare-feu hôte, SSH par clé, cloud-init, dump et restauration PostgreSQL / SQLite, rsync, diagnostic d'un disque qui lâche (journaux système, ne jamais réparer en écriture un disque mourant), migration vérifiée d'un service entre deux machines, lecture de vraies données ouvertes (JSON, RSS, HTML, gzip non annoncé), envoi de fichiers en multipart vers Discord.

## En cours
- Remplacer le disque de sauvegarde, lancer et vérifier la première sauvegarde complète, puis réactiver la sauvegarde nocturne (en y ajoutant le Pi)
- Basculer les téléphones vers le Pi (mots de passe, calendrier, photos) après une dernière synchronisation, puis arrêter ces services sur la tour
- Activer la double authentification du gestionnaire de mots de passe

## Prévu
- Ethernet pour la tour et le Pi, puis Wake-on-LAN de la tour depuis le Pi
- ACL Tailscale écrites à la main
- Réactiver Prometheus et Grafana
- Labo Kubernetes (k3s)
