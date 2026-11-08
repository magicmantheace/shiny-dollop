package ca.wilkins.drabbit.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.withTransform
import ca.wilkins.drabbit.model.PetSummary

/**
 * The drabbit, drawn with Compose Canvas in the desktop app's fur
 * palette (desktop/src/renderer/pet/DrabbitSvg.tsx) so the same pet
 * looks like itself on both screens. Simple shapes on purpose — the
 * v1 art is replaceable in both apps.
 */
private data class Palette(
    val fur: Color,
    val furDark: Color,
    val belly: Color,
    val wing: Color,
    val horn: Color,
    val innerEar: Color,
)

private val PALETTES: Map<String, Palette> = mapOf(
    "ember" to Palette(Color(0xFFCF4433), Color(0xFFA02C1F), Color(0xFFF7DCBA), Color(0xFFE8B64C), Color(0xFFE8B64C), Color(0xFFF2A49B)),
    "meadow" to Palette(Color(0xFF5CB85C), Color(0xFF3E8F3E), Color(0xFFF5EFDC), Color(0xFF2F7D4F), Color(0xFFEFE3C2), Color(0xFFF2C4CE)),
    "royal" to Palette(Color(0xFF8B5CC7), Color(0xFF67409C), Color(0xFFE6D7FA), Color(0xFF5B3A8E), Color(0xFFE8B64C), Color(0xFFD9B8F0)),
    "sky" to Palette(Color(0xFF84C7F0), Color(0xFF5499C9), Color(0xFFFFFFFF), Color(0xFFEEF6FB), Color(0xFFEFE3C2), Color(0xFFF7C9D4)),
    "sunset" to Palette(Color(0xFFF2A93B), Color(0xFFD1811D), Color(0xFFFDEECB), Color(0xFFE2703A), Color(0xFFB3541E), Color(0xFFF7CFA0)),
    "rainbow" to Palette(Color(0xFFB388EB), Color(0xFF8A63C9), Color(0xFFFFFFFF), Color(0xFFF368E0), Color(0xFFE8B64C), Color(0xFFFFD3EC)),
)

private val FALLBACK = PALETTES.getValue("royal")
private val DEAD_GREY = Palette(Color(0xFF9E9E9E), Color(0xFF757575), Color(0xFFE0E0E0), Color(0xFFBDBDBD), Color(0xFFBDBDBD), Color(0xFFBDBDBD))
private val EGG_SHELL = Color(0xFFF5EFDC)
private val EGG_SPECKLE = Color(0xFFCF4433)

@Composable
fun DrabbitCanvas(pet: PetSummary, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        when {
            pet.stage == "egg" -> drawEgg(pet)
            pet.stage == "dead" -> drawDrabbit(pet, DEAD_GREY, dead = true)
            else -> drawDrabbit(pet, PALETTES[pet.fur] ?: FALLBACK, dead = false)
        }
    }
}

private fun DrawScope.drawEgg(pet: PetSummary) {
    val cx = size.width / 2f
    val cy = size.height / 2f
    val w = size.width * 0.52f
    val h = size.height * 0.68f
    drawOval(
        color = EGG_SHELL,
        topLeft = Offset(cx - w / 2f, cy - h / 2f),
        size = Size(w, h),
    )
    // Speckles in the pet's future fur colour.
    val speckle = (PALETTES[pet.fur] ?: FALLBACK).fur
    val spots = listOf(
        Offset(cx - w * 0.22f, cy - h * 0.18f),
        Offset(cx + w * 0.16f, cy - h * 0.02f),
        Offset(cx - w * 0.05f, cy + h * 0.2f),
        Offset(cx + w * 0.24f, cy + h * 0.28f),
    )
    for (spot in spots) {
        drawCircle(color = speckle, radius = w * 0.055f, center = spot)
    }
    if (pet.readyToHatch) {
        // A zigzag crack: ready when you are.
        val crack = Path().apply {
            moveTo(cx - w * 0.3f, cy - h * 0.05f)
            lineTo(cx - w * 0.12f, cy + h * 0.03f)
            lineTo(cx + w * 0.02f, cy - h * 0.05f)
            lineTo(cx + w * 0.16f, cy + h * 0.03f)
            lineTo(cx + w * 0.3f, cy - h * 0.05f)
        }
        drawPath(crack, color = EGG_SPECKLE, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 3f))
    }
    // Ground shadow.
    drawOval(
        color = Color.Black.copy(alpha = 0.12f),
        topLeft = Offset(cx - w * 0.55f, cy + h * 0.52f),
        size = Size(w * 1.1f, h * 0.1f),
    )
}

private fun DrawScope.drawDrabbit(pet: PetSummary, pal: Palette, dead: Boolean) {
    val w = size.width
    val h = size.height
    val cx = w / 2f
    val groundY = h * 0.86f
    val bodyW = w * 0.52f
    val bodyH = h * 0.42f
    val bodyTop = groundY - bodyH
    val droop = if (pet.sick || dead) 14f else 0f

    // Tail: a long furred curl behind the body.
    val tail = Path().apply {
        moveTo(cx + bodyW * 0.34f, groundY - bodyH * 0.25f)
        quadraticBezierTo(cx + bodyW * 0.95f, groundY - bodyH * 0.1f, cx + bodyW * 0.78f, groundY - bodyH * 0.62f)
        quadraticBezierTo(cx + bodyW * 0.68f, groundY - bodyH * 0.3f, cx + bodyW * 0.4f, groundY - bodyH * 0.42f)
        close()
    }
    drawPath(tail, color = pal.furDark)

    // Wings: two cloth wings on the back, raised a little when happy.
    val wingLift = when {
        dead -> 10f
        pet.asleep -> 6f
        pet.mood == "joyful" -> -8f
        else -> 0f
    }
    drawOval(
        color = pal.wing,
        topLeft = Offset(cx - bodyW * 0.52f, bodyTop + bodyH * 0.08f + wingLift),
        size = Size(bodyW * 0.4f, bodyH * 0.44f),
    )
    drawOval(
        color = pal.wing,
        topLeft = Offset(cx + bodyW * 0.14f, bodyTop + bodyH * 0.02f + wingLift),
        size = Size(bodyW * 0.42f, bodyH * 0.5f),
    )

    // Body + belly.
    drawOval(color = pal.fur, topLeft = Offset(cx - bodyW / 2f, bodyTop), size = Size(bodyW, bodyH))
    drawOval(
        color = pal.belly,
        topLeft = Offset(cx - bodyW * 0.26f, bodyTop + bodyH * 0.34f),
        size = Size(bodyW * 0.52f, bodyH * 0.58f),
    )

    // Feet.
    drawOval(color = pal.furDark, topLeft = Offset(cx - bodyW * 0.44f, groundY - bodyH * 0.1f), size = Size(bodyW * 0.3f, bodyH * 0.13f))
    drawOval(color = pal.furDark, topLeft = Offset(cx + bodyW * 0.14f, groundY - bodyH * 0.1f), size = Size(bodyW * 0.3f, bodyH * 0.13f))

    // Head.
    val headR = bodyW * 0.31f
    val headC = Offset(cx, bodyTop - headR * 0.55f + droop)
    drawCircle(color = pal.fur, radius = headR, center = headC)

    // Ears: long, flopped — more droop when sick or gone.
    val earDroop = when {
        dead -> 52f
        pet.sick -> 34f
        pet.asleep -> 26f
        else -> 8f
    }
    drawEar(headC, side = -1, droopDeg = earDroop, pal = pal, headR = headR)
    drawEar(headC, side = 1, droopDeg = earDroop * 0.8f, pal = pal, headR = headR)

    // Horns: two small dragon horns between the ears.
    drawHorn(Offset(headC.x - headR * 0.42f, headC.y - headR * 0.78f), pal.horn, flip = false)
    drawHorn(Offset(headC.x + headR * 0.42f, headC.y - headR * 0.78f), pal.horn, flip = true)

    // Face.
    val eyeY = headC.y - headR * 0.05f
    val eyeDx = headR * 0.38f
    if (dead) {
        drawCrossEye(Offset(headC.x - eyeDx, eyeY), headR * 0.14f)
        drawCrossEye(Offset(headC.x + eyeDx, eyeY), headR * 0.14f)
    } else if (pet.asleep) {
        drawLine(Color(0xFF333333), Offset(headC.x - eyeDx - headR * 0.12f, eyeY), Offset(headC.x - eyeDx + headR * 0.12f, eyeY), strokeWidth = 3f)
        drawLine(Color(0xFF333333), Offset(headC.x + eyeDx - headR * 0.12f, eyeY), Offset(headC.x + eyeDx + headR * 0.12f, eyeY), strokeWidth = 3f)
        // Dream bubbles rising.
        drawCircle(Color(0xFF90CAF9).copy(alpha = 0.8f), radius = 5f, center = Offset(headC.x + headR * 1.05f, headC.y - headR * 0.7f))
        drawCircle(Color(0xFF90CAF9).copy(alpha = 0.6f), radius = 7f, center = Offset(headC.x + headR * 1.3f, headC.y - headR * 1.05f))
        drawCircle(Color(0xFF90CAF9).copy(alpha = 0.45f), radius = 9f, center = Offset(headC.x + headR * 1.6f, headC.y - headR * 1.45f))
    } else {
        drawCircle(Color(0xFF263238), radius = headR * 0.11f, center = Offset(headC.x - eyeDx, eyeY))
        drawCircle(Color(0xFF263238), radius = headR * 0.11f, center = Offset(headC.x + eyeDx, eyeY))
        drawCircle(Color.White, radius = headR * 0.04f, center = Offset(headC.x - eyeDx + 2f, eyeY - 2f))
        drawCircle(Color.White, radius = headR * 0.04f, center = Offset(headC.x + eyeDx + 2f, eyeY - 2f))
    }
    // Nose + mouth.
    drawCircle(color = pal.innerEar, radius = headR * 0.09f, center = Offset(headC.x, headC.y + headR * 0.22f))
    if (pet.sick && !dead) {
        // A wobbly, unwell mouth.
        val mouth = Path().apply {
            moveTo(headC.x - headR * 0.2f, headC.y + headR * 0.45f)
            quadraticBezierTo(headC.x - headR * 0.1f, headC.y + headR * 0.36f, headC.x, headC.y + headR * 0.45f)
            quadraticBezierTo(headC.x + headR * 0.1f, headC.y + headR * 0.54f, headC.x + headR * 0.2f, headC.y + headR * 0.45f)
        }
        drawPath(mouth, color = Color(0xFF333333), style = androidx.compose.ui.graphics.drawscope.Stroke(width = 3f))
        // Sweat drop.
        val drop = Path().apply {
            moveTo(headC.x + headR * 0.95f, headC.y - headR * 0.3f)
            quadraticBezierTo(headC.x + headR * 1.15f, headC.y + headR * 0.05f, headC.x + headR * 0.95f, headC.y + headR * 0.12f)
            quadraticBezierTo(headC.x + headR * 0.75f, headC.y + headR * 0.05f, headC.x + headR * 0.95f, headC.y - headR * 0.3f)
            close()
        }
        drawPath(drop, color = Color(0xFF64B5F6))
    }

    // Ground shadow.
    drawOval(
        color = Color.Black.copy(alpha = 0.12f),
        topLeft = Offset(cx - bodyW * 0.6f, groundY + bodyH * 0.03f),
        size = Size(bodyW * 1.2f, bodyH * 0.12f),
    )
}

private fun DrawScope.drawEar(headC: Offset, side: Int, droopDeg: Float, pal: Palette, headR: Float) {
    val pivot = Offset(headC.x + side * headR * 0.45f, headC.y - headR * 0.72f)
    withTransform({ rotate(side * droopDeg, pivot) }) {
        drawOval(
            color = pal.fur,
            topLeft = Offset(pivot.x - headR * 0.16f, pivot.y - headR * 1.25f),
            size = Size(headR * 0.32f, headR * 1.3f),
        )
        drawOval(
            color = pal.innerEar,
            topLeft = Offset(pivot.x - headR * 0.08f, pivot.y - headR * 1.1f),
            size = Size(headR * 0.16f, headR * 1.0f),
        )
    }
}

private fun DrawScope.drawHorn(base: Offset, color: Color, flip: Boolean) {
    val dir = if (flip) -1f else 1f
    val horn = Path().apply {
        moveTo(base.x - 7f, base.y)
        quadraticBezierTo(base.x + dir * 2f, base.y - 16f, base.x + dir * 10f, base.y - 24f)
        quadraticBezierTo(base.x + dir * 6f, base.y - 8f, base.x + 7f, base.y)
        close()
    }
    drawPath(horn, color = color)
}

private fun DrawScope.drawCrossEye(center: Offset, r: Float) {
    val c = Color(0xFF37474F)
    drawLine(c, Offset(center.x - r, center.y - r), Offset(center.x + r, center.y + r), strokeWidth = 3.5f)
    drawLine(c, Offset(center.x - r, center.y + r), Offset(center.x + r, center.y - r), strokeWidth = 3.5f)
}
