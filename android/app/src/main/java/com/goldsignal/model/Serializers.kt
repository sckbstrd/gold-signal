package com.goldsignal.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.buildClassSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonEncoder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

/** Compact JSON tuples such as ["2026-10-01", 1.74] used for chart series. */
private abstract class TupleSerializer<T>(name: String) : KSerializer<T> {
    override val descriptor: SerialDescriptor = buildClassSerialDescriptor(name)

    abstract fun fromArray(a: JsonArray): T
    abstract fun toArray(value: T): JsonArray

    override fun deserialize(decoder: Decoder): T {
        val input = decoder as? JsonDecoder ?: throw SerializationException("JSON only")
        return fromArray(input.decodeJsonElement().jsonArray)
    }

    override fun serialize(encoder: Encoder, value: T) {
        val output = encoder as? JsonEncoder ?: throw SerializationException("JSON only")
        output.encodeJsonElement(toArray(value))
    }
}

object SeriesPointSerializer : KSerializer<SeriesPoint> by object : TupleSerializer<SeriesPoint>("SeriesPoint") {
    override fun fromArray(a: JsonArray) = SeriesPoint(a[0].jsonPrimitive.content, a[1].jsonPrimitive.double)
    override fun toArray(value: SeriesPoint) = JsonArray(listOf(JsonPrimitive(value.date), JsonPrimitive(value.value)))
}

object MonthValueSerializer : KSerializer<MonthValue> by object : TupleSerializer<MonthValue>("MonthValue") {
    override fun fromArray(a: JsonArray) = MonthValue(a[0].jsonPrimitive.content, a[1].jsonPrimitive.double)
    override fun toArray(value: MonthValue) = JsonArray(listOf(JsonPrimitive(value.month), JsonPrimitive(value.tonnes)))
}

object EquityPointSerializer : KSerializer<EquityPoint> by object : TupleSerializer<EquityPoint>("EquityPoint") {
    override fun fromArray(a: JsonArray) =
        EquityPoint(a[0].jsonPrimitive.content, a[1].jsonPrimitive.double, a[2].jsonPrimitive.double)

    override fun toArray(value: EquityPoint) = JsonArray(
        listOf(JsonPrimitive(value.date), JsonPrimitive(value.strategy), JsonPrimitive(value.benchmark)),
    )
}
