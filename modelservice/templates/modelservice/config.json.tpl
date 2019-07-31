{
    "version": 2,
    "controller": {},
    "workers": [
        {
            "type": "router",
            "realms": [
                {
                    "name": "{{ realm }}",
                    "roles": [
                        {
                            "name": "service",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {
                            "name": "profiler",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {
                            "name": "browser",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        }
                    ]
                }
            ],
            "components": [
                {
                   "type": "class",
                   "realm": "realm1",
                   "role": "service",
                   "classname": "authenticator.AuthenticatorComponent"
                }
            ],
            "transports": [
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": {{ port }},
                        "backlog": 1000
                    },
                    "paths": {
                        "/": {
                            "type": "wsgi",
                            "module": "{{ wsgi_module }}",
                            "object": "{{ wsgi_object }}"
                        },
                        "monitor": {
                            "type": "static",
                            "package": "modelservice",
                            "resource": "static/modelservice/monitor",
                            "options": {
                                "enable_directory_listing": true
                            }
                        },
                        "ws": {
                            "type": "websocket",
                             "auth": {
                                "ticket": {
                                    "type": "static",
                                    "principals": {
                                        "worker": {
                                            "ticket": "===secret!!!===",
                                            "role": "profiler"
                                        }
                                    }
                                },
                                "wampcra": {
                                   "type": "dynamic",
                                   "authenticator": "world.simpl.authenticate"
                                },
                                "anonymous": {
                                    "type": "static",
                                    "role": "service"
                                }
                            },
                            "options": {
                                "enable_webstatus": false,
                                "max_frame_size": 1048576,
                                "max_message_size": 0,
                                "auto_fragment_size": 65536,
                                "fail_by_drop": true,
                                "open_handshake_timeout": 2500,
                                "close_handshake_timeout": 1000,
                                "auto_ping_interval": 10000,
                                "auto_ping_timeout": 300000,
                                "auto_ping_size": 4
                            }
                        },
                        "callback": {
                            "type": "webhook",
                            "realm": "{{ realm }}",
                            "role": "service",
                            "options": {
                                "topic": "{{ ROOT_TOPIC }}.model.game.webhook_forward"
                            }
                        }{% if DEBUG %},
                        "publish": {
                            "type": "publisher",
                            "realm": "realm1",
                            "role": "service"
                        },
                        "call": {
                            "type": "caller",
                            "realm": "realm1",
                            "role": "service"
                        }
                        {% endif %}
                    }
                }
            ]
        },
        {
            "type": "guest",
            "executable": "manage.py",
            "arguments": ["run_guest"],
            "options": {
                "env": {
                    "vars": {
                        "HOSTNAME": "{{ hostname }}",
                        "PORT": "{{ port }}"
                    }
                }
            }
        }
    ]
}
