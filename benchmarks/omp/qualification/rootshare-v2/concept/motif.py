"""Rootshare: a bespoke R shelters a seed-shaped negative space."""

from pathlib import Path

from logo_maker.motif import Motif

m = Motif()


def curve(start, control1, control2, end, steps=64):
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        points.append(
            tuple(
                u * u * u * start[k]
                + 3 * u * u * t * control1[k]
                + 3 * u * t * t * control2[k]
                + t * t * t * end[k]
                for k in (0, 1)
            )
        )
    return points


outline = [(270, 776), (270, 190)]
outline += curve(outline[-1], (270, 178), (282, 170), (294, 170))
outline.append((475, 170))
outline += curve(outline[-1], (610, 170), (692, 245), (692, 355))
outline += curve(outline[-1], (692, 441), (646, 499), (574, 526))
outline.append((760, 768))
outline += curve(outline[-1], (770, 781), (765, 790), (752, 790))
outline.append((626, 790))
outline += curve(outline[-1], (614, 790), (607, 786), (601, 776))
outline.extend([(445, 535), (408, 535), (408, 776)])
outline += curve(outline[-1], (408, 785), (401, 790), (393, 790))
outline.append((285, 790))
outline += curve(outline[-1], (276, 790), (270, 784), (270, 776))
seed = [(545, 253)]
seed += curve(seed[-1], (635, 325), (594, 427), (465, 465))
seed += curve(seed[-1], (395, 368), (421, 291), (545, 253))
seed_shape = m.polygon(seed)
body = m.difference(m.polygon(outline), seed_shape)
membrane = m.intersection(m.difference(m.stroke(seed_shape, 50), m.stroke(seed_shape, 35)), body)
m.add("body", body, fill="#B95E3F", role="primary")
m.add("seed_membrane", membrane, fill="#E4CBA7", role="accent", layer=1)
m.save(Path(__file__).parent)
