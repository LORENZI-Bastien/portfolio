# Homelab : source de vérité

Ce fichier alimente la section « Homelab » du site (`index.html#homelab`) et du profil GitHub.
Une tâche planifiée le relit chaque jour à 5 h et met à jour les deux si quelque chose a changé.

**Règles :** rien de sensible ici (pas d'IP, de nom de domaine, de nom de machine, de compte, d'identifiant ni de nombre d'entrées). Ce fichier n'est pas servi par le site (`_redirects`).

*Dernière mise à jour : 9 novembre 2026*

## En bref
Homelab sobre en énergie : tout tourne sur un Raspberry Pi 5 allumé 24 h/24, en conteneurs Docker. Accès à distance uniquement par Tailscale, aucun port ouvert sur la box, tous les services en HTTPS.

## Évolution de l'architecture
- **Au départ :** une tour Windows de récupération (Docker sous WSL2, GPU) faisait tourner 14 conteneurs, dont une IA locale.
- **7 novembre 2026 :** le Pi devient le serveur 24 h/24, la tour ne devait plus être réveillée que pour l'IA et les tâches lourdes.
- **9 novembre 2026 :** l'IA locale est abandonnée et tous les services tournent sur le Pi. Les services de la tour sont arrêtés (rien n'a été supprimé), et la tour sera vendue une fois les disques déplacés.

## Machines
| Machine | Matériel | Système | Rôle |
|---|---|---|---|
| Raspberry Pi 5 | 8 Go, SSD NVMe 256 Go | Raspberry Pi OS 64 bits, Docker | Serveur unique, allumé 24 h/24 |
| Tour (en retrait) | Ryzen 5 1600, 16 Go, GTX 1660 Super 6 Go | Windows 10, WSL2, Docker Desktop | Services arrêtés, garde encore les disques de données en attendant le boîtier |

## Services (sur le Pi)
- **Vaultwarden** : gestionnaire de mots de passe compatible Bitwarden
- **Radicale** : calendrier partagé (CalDAV)
- **Immich** : photos, sauvegarde automatique des téléphones, reconnaissance de visages sur le processeur
- **AdGuard Home** : DNS filtrant de tout le VPN, résolveur amont en DoH
- **n8n** : automatisations
- **Uptime Kuma** : supervision de disponibilité
- **Home Assistant** : domotique
- **Homepage** : portail d'accueil
- **Point politique quotidien** : projet maison (voir plus bas)

## Projet maison : point politique quotidien
Petit service en Python (sans dépendance), dans un conteneur Docker sur le Pi, sans aucun port ouvert. Chaque matin, il lit les données ouvertes officielles (scrutins de l'Assemblée nationale, scrutins et textes du Sénat, Panorama des lois de vie-publique) et envoie un résumé neutre sur un salon Discord : votes importants adoptés ou rejetés, détail par groupe politique masqué, et fichier joint avec le vote nominatif des députés et sénateurs. Anti-doublon par fichier d'état, tolérance aux pannes d'une source, 10 tests unitaires. Code source : [outils/point-politique](outils/point-politique/).

## Réseau
- Un seul réseau local derrière la box, pas de VLAN
- Tailscale (WireGuard) relie le Pi, les ordinateurs et les téléphones, à la maison comme en 4G
- MagicDNS, `tailscale serve` comme reverse proxy HTTPS, certificats Let's Encrypt
- AdGuard Home sur le Pi sert de DNS filtrant à tout le VPN, avec un plan de repli si le Pi tombe

## Sécurité
- Aucun service exposé sur Internet, aucune redirection de port
- Ports des conteneurs liés à la machine locale uniquement
- Pare-feu hôte, activé avec un retour arrière automatique
- SSH par clé, mises à jour de sécurité automatiques
- Secrets dans des fichiers à accès restreint, jamais dans le code
- Inscriptions fermées sur le gestionnaire de mots de passe

## Sauvegardes
- Choix : sauvegardes versionnées sur un disque séparé (rsync avec instantanés datés + dumps cohérents des bases) plutôt qu'un RAID, qui recopie aussi les erreurs
- Le premier disque de sauvegarde s'est révélé défaillant : **pas encore de sauvegarde automatique valide**, c'est le point faible actuel
- En attendant : export chiffré du coffre de mots de passe hors du serveur, photos encore présentes sur les disques de la tour

## Problèmes résolus
- Deux machines invisibles sur le VPN : connectées avec deux comptes différents
- Données « perdues » au redémarrage : Docker démarrait avant WSL, script de démarrage qui attend
- Disque de sauvegarde défaillant : diagnostic par les journaux et `chkdsk` en lecture seule
- Migration de services vers le Pi : export des bases, transfert chiffré, SHA256, comparaison des comptages
- IA dans 6 Go de VRAM (avant l'abandon de l'IA locale) : modèles 4-8 B, un seul chargé à la fois
- Reverse proxy refusé par Home Assistant : déclarer le proxy de confiance
- Mots de passe d'admin perdus : réinitialisation sans perte de données, après sauvegarde des bases

## Ce que j'ai appris
WSL2, Docker Compose (volumes, bind mounts, profils, limites mémoire), Tailscale et WireGuard, reverse proxy et TLS, DNS filtrant et DoH, pare-feu hôte, SSH par clé, cloud-init, dump et restauration PostgreSQL / SQLite, rsync, diagnostic d'un disque qui lâche (journaux système, ne jamais réparer en écriture un disque mourant), migration vérifiée de services Docker d'une machine Windows/WSL vers un serveur ARM, lecture de vraies données ouvertes (JSON, RSS, HTML, gzip non annoncé), envoi de fichiers en multipart vers Discord. Et surtout : sans IA locale, un serveur basse consommation suffit largement.

## En cours
- Brancher un disque de 2 To en USB sur le Pi, lancer et vérifier la première sauvegarde complète, puis activer la sauvegarde nocturne
- Activer la double authentification du gestionnaire de mots de passe

## Prévu
- Après Noël : boîtier 4 baies USB sur le Pi (disque de données de 4 To + disque de 1 To récupéré) pour y remettre Jellyfin et Navidrome
- Ensuite : vendre la tour
- ACL Tailscale écrites à la main
- Labo Kubernetes (k3s)
