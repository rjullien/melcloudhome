# État d'un climatiseur ATA : mode, activité et liaison cloud

Un état `heat` signifie que le climatiseur est déclaré allumé en mode chauffage
par MELCloud. Il ne prouve pas que le compresseur tourne ou que la pièce reçoit
de la chaleur à cet instant. Une consigne de 19,5 °C est une température demandée,
pas un relevé d'activité.

Ce guide décrit le fork et distingue trois notions : le mode demandé,
l'activité estimée et les liaisons cloud. Les identifiants ci-dessous sont
indicatifs : la langue, les anciens enregistrements et les renommages peuvent
les modifier. Ainsi, `climate.<maison>_melcloudhome_<id>_climate` peut être
un identifiant personnalisé ; le format par défaut figure dans la
[référence des entités](entities.md).

## Mode affiché : `hvac_mode`

Dans `custom_components/melcloudhome/climate_ata.py`, la propriété `hvac_mode`
lit le modèle de l'unité :

1. Si le modèle est absent ou si `power` est faux, elle retourne `off`.
2. Sinon, `ATA_TO_HA_HVAC_MODE` dans `const_ata.py` traduit `operation_mode` :

| MELCloud `OperationMode` | État Home Assistant |
| --- | --- |
| `Heat` | `heat` |
| `Cool` | `cool` |
| `Automatic` | `auto` |
| `Dry` | `dry` |
| `Fan` | `fan_only` |
| Valeur inconnue | `auto` |

`AirToAirUnit.from_dict` dans `api/models_ata.py` lit la liste `settings` de
`/context` : `Power`, `OperationMode`, `SetTemperature`, `RoomTemperature` et
`InStandbyMode`. Les booléens sont convertis par `parse_bool` dans
`api/parsing.py` : `True` ou la chaîne `true` sans distinction de casse donnent
vrai ; une valeur absente donne faux. Si `OperationMode` est absent, le modèle
utilise `Heat`. Cela diffère d'une valeur présente mais inconnue, traduite en
`auto` par l'entité. Les températures absentes restent `None`.

Ainsi, `heat` avec une consigne de 19,5 °C correspond à `Power=true`,
`OperationMode=Heat` et `SetTemperature=19.5` dans le modèle courant.
Le mode est celui demandé et rapporté par le cloud, pas un retour matériel du
compresseur. La disponibilité est séparée : `ATAEntityBase.available` dans
`const_ata.py` peut faire afficher `unavailable` si le coordinateur est en échec,
si l'unité manque ou si elle est en erreur.

## Actualisation des données

`MELCloudHomeCoordinator._async_update_data` dans `coordinator.py` appelle
`client.get_user_context`. L'intervalle normal est de 60 secondes
(`UPDATE_INTERVAL` dans `const.py`). Ce n'est pas une assurance de fraîcheur :
`_tolerate_poll_failure` conserve les dernières données pendant certaines pannes
transitoires.

Le WebSocket, activé par défaut mais désactivable, accélère ce mécanisme.
`_async_setup_websocket` associe `_on_ws_delta` aux changements d'unité.
Ce dernier date `ws_last_delta_at` puis demande un rafraîchissement regroupé
avec `async_request_refresh_debounced`. Les deltas de réglages ne remplacent
donc pas directement le modèle : ils déclenchent une nouvelle lecture cloud.
Les événements de perte/rétablissement de communication ont un traitement
distinct, décrit plus bas.

## Activité estimée : `hvac_action`

La propriété `hvac_action` de `climate_ata.py` délègue à
`HVACActionDeterminer.determine_action` dans `climate_helpers.py`. L'ordre des
tests est important :

1. Modèle absent : pas d'action (`None`).
2. `Power=false` : `off`, même si un indicateur d'attente est présent.
3. `InStandbyMode=true` : `preheating` en `Heat` ou `Automatic` ; `idle` dans
   les autres modes. C'est l'interprétation du fork de l'attente signalée par
   MELCloud, pas un relevé du préchauffage électrique.
4. Sans attente, application des règles suivantes.

Avec température ambiante et consigne disponibles,
`_determine_action_with_temps` utilise `HYSTERESIS_THRESHOLD = 0.5` °C :

| Mode | Condition | `hvac_action` |
| --- | --- | --- |
| `Heat` | Ambiante strictement inférieure à consigne − 0,5 °C | `heating` |
| `Heat` | Sinon | `idle` |
| `Cool` | Ambiante strictement supérieure à consigne + 0,5 °C | `cooling` |
| `Cool` | Sinon | `idle` |
| `Automatic` | Toutes températures | `idle` |
| `Dry` | Toutes températures | `drying` |
| `Fan` | Toutes températures | `fan` |
| Mode inconnu | Toutes températures | `idle` |

À l'égalité avec le seuil, le résultat est `idle`. Pour une consigne de
19,5 °C en `Heat`, `heating` nécessite une température strictement inférieure
à 19,0 °C. Bien que le code parle d'hystérésis, ce calcul ne mémorise pas
l'action précédente : il applique un seuil à chaque évaluation.

Si l'une des deux températures manque, `_determine_action_without_temps`
retourne `drying` pour `Dry`, `fan` pour `Fan`, et `idle` pour tous les autres
modes, dont `Heat`, `Cool` et `Automatic`.

En automatique, le fork ne déduit jamais chauffage ou refroidissement de
l'écart à la consigne. Les réglages capturés n'offrent pas de mode réel
chauffage/refroidissement ; cette déduction avait notamment confondu attente
chauffage et refroidissement. `idle` ne prouve donc pas que le compresseur
est arrêté. De même, `heating` est une estimation fondée sur les températures.
La granularité de la température ambiante dépend de l'unité ; le pas de
consigne de 0,5 °C décrit dans l'API ne démontre pas la résolution de sa sonde.

## Quelles entités répondent à « est-il allumé ? »

| Question | Entité ou champ | Source |
| --- | --- | --- |
| L'unité est-elle déclarée allumée, et dans quel mode ? | État de `climate.melcloudhome_<id>_climate` | `settings.Power` et `settings.OperationMode` |
| Quelle température est demandée ? | Champ `temperature` du climatiseur | `settings.SetTemperature` |
| Quelle activité est estimée ? | Champ `hvac_action` du climatiseur | Mode, attente et écart `RoomTemperature` / `SetTemperature` |
| L'unité attend-elle ? | `binary_sensor.melcloudhome_<id>_standby`, ou champ `in_standby_mode` | `settings.InStandbyMode` |
| L'unité communique-t-elle avec MELCloud ? | `binary_sensor.melcloudhome_<id>_connection_state` | `isConnected` de `/context` et événements de communication WebSocket |
| Le canal temps réel de l'intégration est-il connecté ? | Capteur binaire « Real-time updates », champ `last_delta_at` | Liaison WebSocket et date du dernier delta reçu |
| Une consommation a-t-elle été rapportée sur une période ? | `sensor.melcloudhome_<id>_energy` et ses variations | Rapports d'énergie cumulée en kWh |

Les capteurs d'attente et de liaison par unité sont définis dans
`binary_sensor_ata.py`. En français, le suffixe d'attente peut être
`_en_attente`. Une unité peut être éteinte mais connectée au cloud, ou déclarée
en chauffage alors que sa communication vient d'être perdue.

Pour la liaison cloud, `effective_connection_is_on` et `_on_ws_communication`
dans `coordinator.py` appliquent immédiatement `unitCommunicationLost` ou
`unitCommunicationRestored`. Les champs `last_communication_lost` et
`last_communication_restored` datent ces événements reçus ; ils peuvent être
absents si aucun événement n'a été reçu pendant cette session. Le champ
`is_connected` garde la valeur brute REST. Après plus d'un sondage en désaccord,
`_reconcile_one_unit_communication` rend la priorité à REST. Si `isConnected`
manque, le capteur est considéré connecté par compatibilité : son état `on`
n'est alors pas une preuve positive de communication. La déconnexion seule ne
rend pas indisponibles les autres entités.

Le capteur « Real-time updates » de `binary_sensor.py` concerne le WebSocket
de l'entrée d'intégration, pas chaque unité. Son état suit `ws_connected` ;
`last_delta_at` date le dernier delta reçu, quelle que soit l'unité concernée.
Une longue absence de delta peut simplement signifier qu'aucun réglage ne
change. Ce capteur ne vérifie ni l'alimentation du climatiseur ni la santé
globale du service MELCloud.

## Limites : peut-on savoir si le compresseur tourne ?

L'[API ATA documentée et capturée](api/ata-api-reference.md) n'expose pas
d'état marche/arrêt du compresseur, de fréquence du compresseur ni de puissance
électrique instantanée permettant de le confirmer. Le champ `Power` est un
booléen de commande, pas une puissance en watts. Cela ne démontre pas qu'aucune
autre API ou aucun autre matériel ne peut fournir ces données.

Les variations du compteur d'énergie sur des périodes horaires donnent un
indice indirect et retardé de consommation. Elles ne localisent pas un
démarrage à la seconde et ne distinguent pas à elles seules compresseur,
ventilation et veille. Pour un relevé électrique fiable et instantané,
utiliser un compteur de puissance externe adapté au circuit ; sur un système
multi-split, un relevé sur l'unité extérieure agrège les unités desservies.

En pratique : utiliser le mode pour la commande, l'attente pour interpréter
l'état rapporté, la liaison pour diagnostiquer le lien cloud, et un relevé
électrique externe pour confirmer la consommation réelle.
