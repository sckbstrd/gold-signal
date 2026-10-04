package com.goldsignal

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import com.goldsignal.core.designsystem.GoldSignalTheme
import com.goldsignal.ui.GoldSignalNavHost

/** AppCompatActivity (a ComponentActivity) so per-app language switching works on API 26-32. */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            GoldSignalTheme {
                GoldSignalNavHost()
            }
        }
    }
}
