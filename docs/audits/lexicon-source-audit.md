# Lexicon source audit

POS presence is measured after canonical normalization. Preset generation removes a
candidate when that normalized POS is absent from the complete snapshot index.
Multiword phrases may match a compatible lexical POS rather than only `phrase`.
Example absence is reported separately and never causes removal.

| Exam | Words | Word+POS | Wiki lexeme | Wiki POS | Wiki example | WordNet example | WordNet-only |
|---|---:|---:|---:|---:|---:|---:|---:|
| ZK | 1,603 | 2,783 | 1,603 (100.0%) | 2,693 (96.77%) | 2,624 | 1,600 | 29 (1.04%) |
| GK | 3,677 | 5,777 | 3,676 (99.97%) | 5,645 (97.72%) | 5,445 | 3,290 | 62 (1.07%) |
| CET4 | 3,849 | 5,793 | 3,848 (99.97%) | 5,711 (98.58%) | 5,537 | 3,495 | 56 (0.97%) |
| CET6 | 5,407 | 7,807 | 5,407 (100.0%) | 7,712 (98.78%) | 7,385 | 4,444 | 87 (1.11%) |
| KAOYAN | 4,801 | 7,216 | 4,801 (100.0%) | 7,121 (98.68%) | 6,850 | 4,292 | 75 (1.04%) |
| IELTS | 5,040 | 7,327 | 5,038 (99.96%) | 7,201 (98.28%) | 6,659 | 4,128 | 83 (1.13%) |
| TOEFL | 6,974 | 9,382 | 6,972 (99.97%) | 9,273 (98.84%) | 8,632 | 5,083 | 155 (1.65%) |
| GRE | 7,504 | 9,964 | 7,503 (99.99%) | 9,874 (99.1%) | 9,038 | 4,686 | 190 (1.91%) |

`WordNet-only` means WordNet has an indexed example for that word+POS while Wiktionary
has no example passing TypEng's current filters. It does not mean Wiktionary lacks the word.

## ZK samples

- WordNet-only examples: above/adj, accent/v, another/adj, any/adj, atlantic/adj, both/adj, colour/v, culture/v, each/adj, enough/adj, every/adj, few/adj, few/n, honour/v, much/adj, much/n, no/adj, none/adj, plane/adj, plane/v, schoolbag/n, size/adj, some/adj, spread/adj, such/adj
- Lexemes absent from snapshot: none
- Normalized word+POS misses: ago/adv, another/adj, any/adj, anybody/n, asleep/adv, both/adj, both/adv, centre/adj, china/adj, church/adj, club/adj, daughter/adj, dozen/adj, dvd/abbr, each/adj, eighth/num, either/adj, enemy/adj, enough/adj, every/adj, fall/adj, few/adj, field/adj, fifth/num, first/num
- Wiktionary word+POS without a usable example: above/adj, accent/v, atlantic/adj, bright/adv, candle/v, captain/v, cd-rom/n, chopsticks/n, colour/v, comfortable/n, crayon/v, culture/v, daily/adv, east/adv, enough/interj, festival/adj, few/n, goodbye/interj, granddaughter/n, grandma/n, grandpa/n, gymnasium/n, ham/v, holiday/v, honour/v

## GK samples

- WordNet-only examples: above/adj, absurd/n, accent/v, ahead/adj, another/adj, any/adj, atlantic/adj, both/adj, british/adj, challenging/adj, colour/v, cordless/adj, culture/v, dam/v, dot/v, downtown/n, each/adj, enough/adj, every/adj, fax/v, few/adj, few/n, graduate/adj, honour/v, hug/n
- Lexemes absent from snapshot: cance
- Normalized word+POS misses: ago/adv, ahead/adj, aluminium/adj, another/adj, any/adj, anybody/n, asleep/adv, beddings/adj, beddings/v, both/adj, both/adv, broad/adv, cance/n, centre/adj, china/adj, church/adj, club/adj, daughter/adj, dot/v, dozen/adj, dvd/abbr, each/adj, eastern/n, eighth/num, either/adj
- Wiktionary word+POS without a usable example: abnormal/n, above/adj, absurd/n, accent/v, afterward/adv, agriculture/n, ankle/n, antarctic/n, are/n, artist/n, atlantic/adj, backache/n, bacterium/n, barber/n, barbershop/n, bathrobe/n, birdcage/n, bookcase/n, bookshelf/n, bookshop/n, bookstore/n, bowling/n, bridegroom/n, bright/adv, british/adj

## CET4 samples

- WordNet-only examples: accent/v, alert/v, arabian/adj, atlantic/adj, brisk/v, catalog/n, circumference/n, civilize/v, cliff/n, core/v, culture/v, dam/v, discipline/v, dot/v, essential/n, excess/adj, fax/v, graduate/adj, honour/v, industrialize/v, jewel/v, judgement/n, licence/v, major/v, mediterranean/adj
- Lexemes absent from snapshot: reservior
- Normalized word+POS misses: aluminium/adj, asleep/adv, auto/pref, b.c./phrase, broad/adv, cabinet/adj, centre/adj, chamber/adj, church/adj, club/adj, crack/adv, distress/adj, dot/v, dozen/adj, eastern/n, enemy/adj, extension/adj, fahrenheit/n, fatigue/adj, fellow/adj, fleet/adv, hedge/adj, horn/adj, ice-cream/adj, jazz/adj
- Wiktionary word+POS without a usable example: abnormal/n, accent/v, afterward/adv, agriculture/n, alert/v, aluminum/n, ankle/n, arabian/adj, artist/n, atlantic/adj, ax/n, barber/n, bold/n, brass/v, brisk/v, bruise/n, cafeteria/n, candle/v, captain/v, catalog/n, centigrade/adj, certificate/v, champion/v, circumference/n, civilize/v

## CET6 samples

- WordNet-only examples: absurd/n, alert/v, arabian/adj, bleach/n, brisk/v, catalog/n, circumference/n, civilize/v, cliff/n, core/v, cozy/adj, culture/v, dam/v, decimal/adj, destine/v, discipline/v, earnings/n, eligible/adj, essential/n, esthetic/adj, excess/adj, graduate/adj, honour/v, hug/n, hurrah/n
- Lexemes absent from snapshot: none
- Normalized word+POS misses: aluminium/adj, attent/v, cabinet/adj, centre/adj, chamber/adj, crack/adv, distress/adj, dynamical/n, elapse/n, extension/adj, fahrenheit/n, fatigue/adj, fellow/adj, first-rate/adv, fleet/adv, fore/prep, fossil/adj, foul/adv, ham/adj, hardy/adv, hedge/adj, horn/adj, hush/interj, leisure/adj, lifetime/adj
- Wiktionary word+POS without a usable example: abnormal/n, absurd/n, accessary/n, affective/adj, afterward/adv, agriculture/n, alert/v, analogue/n, ankle/n, anode/n, antarctic/n, arabian/adj, bacterium/n, bankrupt/n, barley/n, bleach/n, blond/n, blunder/n, bold/n, bridegroom/n, brisk/v, bruise/n, buddhism/n, bushel/v, cafeteria/n

## KAOYAN samples

- WordNet-only examples: absurd/n, accent/v, acclaim/n, alert/v, brisk/v, catalog/n, circumference/n, civilize/v, cliff/n, core/v, culture/v, dam/v, decimal/adj, discipline/v, dot/v, downtown/n, dramatize/v, eligible/adj, essential/n, excerpt/n, excess/adj, fabulous/adj, fax/v, graduate/adj, hug/n
- Lexemes absent from snapshot: none
- Normalized word+POS misses: asleep/adv, auto/pref, broad/adv, bully/adv, cabinet/adj, centre/adj, chamber/adj, church/adj, club/adj, crack/adv, distress/adj, dot/v, dozen/adj, eastern/n, elapse/n, enemy/adj, extension/adj, fatigue/adj, fellow/adj, fleet/adv, fore/prep, fossil/adj, foul/adv, ham/adj, hedge/adj
- Wiktionary word+POS without a usable example: abnormal/n, absurd/n, accent/v, acclaim/n, acrobat/n, afterward/adv, agriculture/n, alert/v, aluminum/n, analogue/n, ankle/n, appal/v, artist/n, auction/v, bacterium/n, bankrupt/n, barber/n, blackmail/n, blunder/n, bold/n, bowling/n, brass/v, brisk/v, bruise/n, cab/v

## IELTS samples

- WordNet-only examples: absurd/n, acclaim/n, affairs/n, annuity/n, applied/adj, aquatic/adj, bilateral/adj, bleach/n, brisk/v, british/adj, catalog/n, challenging/adj, circumference/n, cliff/n, culture/v, dam/v, decimal/adj, departmental/adj, destine/v, details/n, discipline/v, dot/v, downtown/n, effects/n, eligible/adj
- Lexemes absent from snapshot: first-aid, water-clock
- Normalized word+POS misses: account for/phrase, advertising/adj, bedsit/v, booklist/phrase, bring about/phrase, buck/adj, bully/adv, cabinet/adj, centre/adj, chamber/adj, church/adj, cliche/adj, club/adj, crack/adv, distress/adj, dot/v, drop-out/phrase, eastern/n, elapse/n, extension/adj, fahrenheit/n, fall/adj, fatigue/adj, field/adj, fifth/num
- Wiktionary word+POS without a usable example: abnormal/n, absurd/n, acclaim/n, accuser/n, activities/n, adults/n, advantages/n, advantages/v, advertisements/n, affairs/n, agencies/n, agriculture/n, amphibian/adj, animals/n, ankle/n, annuity/n, antarctic/n, antibiotic/adj, antibiotics/n, apes/n, apes/v, applied/adj, approaches/n, aquarium/n, aquatic/adj

## TOEFL samples

- WordNet-only examples: absurd/n, acclaim/n, agrarian/adj, alert/v, amplification/n, aquatic/adj, arbitration/n, armory/n, asphalt/v, auditory/adj, barbarian/adj, beaded/adj, bilateral/adj, bleach/n, brisk/v, calibre/n, canter/v, capillary/adj, checkout/n, circumference/n, cleft/adj, cliff/n, comprehensible/adj, core/v, cozy/adj
- Lexemes absent from snapshot: broad-brimmed, thousand-fold
- Normalized word+POS misses: accordion/adj, account for/phrase, aglow/adv, alkali/adj, aluminium/adj, asphalt/adj, asteroid/adj, broad-brimmed/adj, bully/adv, cabinet/adj, chamber/adj, contour/adj, crack/adv, crosscut/adj, daisy/adj, distress/adj, dot/v, elapse/n, emigrant/adj, entrenched/adj, envelop/n, exponent/adj, extension/adj, facsimile/adj, fahrenheit/n
- Wiktionary word+POS without a usable example: abnormal/n, abrasive/n, absurd/n, acclaim/n, acclaimed/v, acoustical/adj, acupuncture/v, adjunct/adj, adulteration/n, aesthetical/adj, affective/adj, agrarian/adj, agriculture/n, airsickness/n, alert/v, alkali/n, aluminum/n, alumnus/n, amplification/n, annex/n, antibiotic/adj, antiquate/v, aquarium/n, aquatic/adj, arbitration/n

## GRE samples

- WordNet-only examples: absurd/n, acclaim/n, acquired/adj, agglomerate/adj, agrarian/adj, alert/v, ambulatory/n, anaerobic/adj, annexation/n, aquatic/adj, armory/n, bale/v, battalion/n, bawdy/adj, bleach/n, bombardment/n, brisk/v, calibre/n, capillary/adj, catalog/n, centrifugal/adj, circumference/n, cleft/adj, cloture/v, comprehensible/adj
- Lexemes absent from snapshot: other-directed
- Normalized word+POS misses: aboveboard/adv, alkali/adj, aluminium/adj, asteroid/adj, berserk/adv, biped/adj, buck/adj, bully/adv, cabinet/adj, crack/adv, distress/adj, dummy/adj, emissary/adj, exponent/adj, facsimile/adj, fatigue/adj, fleet/adv, flunk/n, forensic/n, foul/adv, functionary/adj, gainsay/n, goggle/adj, gormandize/n, hack/adj
- Wiktionary word+POS without a usable example: abrasive/n, abstentious/adj, abstinent/n, absurd/n, acarpous/adj, acclaim/n, acclimate/v, acquired/adj, acrobat/n, adjunct/adj, adlib/v, adulate/v, aeronautics/n, agglomerate/adj, agglomerate/n, agrarian/adj, agronomy/n, albino/n, alert/v, alias/n, alibi/v, alimentary/adj, alkali/n, ambulatory/n, amphibian/adj
