var goodcells = /^\s*(?:good|bmi)?\s?(?:unit|cell)s?\s?[:-]\s*\n*(.*)$/gim;
var cellnames = /(\d{1,3})\s?(\w{1})/gim;
var parsecell = /(\d{1,3})\s?(\w{1})/;
var parsetime = /^(?:(\d{0,2}):)?(\d{1,2}):(\d{0,2}\.?\d*)$/;

function BMI(idx, info, notes) {
    this.idx = idx;
    try {
        this.cells = goodcells.exec(notes)[1].match(cellnames);
    } catch (e) {
        this.cells = [];
    }

    this.info = info;
    this.plxinfo = info['_plxinfo'];
    delete info['_plxinfo']

    this.available = {};
    this.selected = {};

    if (this.plxinfo !== null) {
        for (var i = 0; i < this.plxinfo.units.length; i++) {
            var name = this.plxinfo.units[i][0];
            name += String.fromCharCode(this.plxinfo.units[i][1]+96);
            this.remove(name);
        }

        this._bindui();
        this.cancel();
    }
}
BMI.zeroPad = function(number, width) {
    width -= number.toString().length;
    if ( width > 0 ) {
        var w = /\./.test(number) ? 2 : 1;
        return new Array(width + w).join('0') + number;
    }
    return number + "";
}
BMI.hms = function(sec) {
    var h = Math.floor(sec / 60 / 60);
    var m = Math.floor(sec / 60 % 60);
    var s = Math.round(sec % 60);
    if (h > 0)
        return h+':'+BMI.zeroPad(m,2)+':'+BMI.zeroPad(s,2);
    return m+':'+BMI.zeroPad(s,2);
}
BMI.ptime = function(t) {
    var chunks = parsetime.exec(t);
    try {
        var secs = parseInt(chunks[2]) * 60;
        secs += parseFloat(chunks[3]);
        if (chunks[1] !== undefined)
            secs += parseInt(chunks[1]) * 60 * 60;

        return secs;
    } catch (e) {
        return null;
    }
}
BMI.swap = function(name, src, dst, dstname) {
    if (dst[name] === undefined) {
        var obj;
        if (src[name] !== undefined) {
            obj = src[name].remove()
            delete src[name];
        } else {
            obj = $("<option>"+name+"</option>");
        }

        var names = [name];
        for (var n in dst)
            names.push(n)
        dst[name] = obj;

        if (names.length == 1)
            return $('#'+dstname).append(obj);

        //Rudimentary lexical sort
        names.sort(function(b, a) {
            var an = parsecell.exec(a);
            var bn = parsecell.exec(b);
            var chan = parseInt(bn[1], 10) - parseInt(an[1], 10);
            var chr = (bn[2].charCodeAt(0) - an[2].charCodeAt(0));
            return chan + chr / 10;
        });
        var idx = names.indexOf(name);
        if (idx == 0)
            dst[names[idx+1]].before(obj);
        else
            dst[names[idx-1]].after(obj);
    }
}
BMI.prototype.add = function(name) {
    BMI.swap(name, this.available, this.selected, 'cells');
}
BMI.prototype.remove = function(name) {
    BMI.swap(name, this.selected, this.available, 'available');
}
BMI.prototype.parse = function(cells, addAvail) {
    var names = cells.match(cellnames);
    if (addAvail) {
        for (var i = 0, il = names.length; i < il; i++) {
            this.remove(names[i]);
        }
    } else {
        $("#cells option").each(function(idx, obj) {
            this.remove($(obj).text());
        }.bind(this));

        for (var i = 0, il = names.length; i < il; i++) {
            this.add(names[i]);
        }
        this.update();
    }
}
BMI.prototype.update = function(names) {
    var names = [];
    $('#cells option').each(function(idx, val) {
        names.push($(val).text());
    })
    $('#cellnames').val(names.join(', '));
}

BMI.prototype.set = function(name) {
    var info = this.info[name];
    $("#cells option").each(function(idx, obj) {
        this.remove($(obj).text());
    }.bind(this));

    for (var i = 0; i < info.units.length; i++) {
        var unit = info.units[i];
        var n = unit[0] + String.fromCharCode(unit[1]+96);
        this.add(n);
    }
    this.update();

    $("#bmibinlen").val(info.binlen);
    $("#tstart").val(BMI.hms(info.tslice[0]));
    $("#tend").val(BMI.hms(info.tslice[1]));
    $("#tslider").slider("values", info.tslice);
    $("#bmiclass option").each(function(idx, obj) {
        if ($(obj).text() == info.cls)
            $(obj).attr("selected", "selected");
    });
}
BMI.prototype.new = function() {
    $("#cells option").each(function(idx, obj) {
        this.remove($(obj).text());
    }.bind(this));
    $("#bmibinlen").val("0.1");
    $("#bminame").replaceWith("<input id='bminame'>");
    $("#bminame").val(this.plxinfo.name);
    for (var i = 0; i < this.cells.length; i++) 
        this.add(this.cells[i]);
    $(".bmibtn").show();
    $("#bmi input,select,textarea").attr("disabled", null);
    this.update();
}
BMI.prototype.cancel = function() {
    $("#bmi input,select,textarea").attr("disabled", "disabled");
    $("#bminame").replaceWith("<select id='bminame' />");
    var i = 0;
    for (var name in this.info) {
        $("#bminame").append('<option>'+name+'</option>');
        i++;
    }

    if (i < 1)
        return this.new();

    $(".bmibtn").hide();
    $("#bminame").append("<option value='new'>Create New</option>");
    this.set($("#bminame option:first").text());

    var _this = this;
    $("#bminame").change(function(e){
        if (this.value == 'new')
            _this.new();
        else
            _this.set(this.value);
    })
}
BMI.prototype._bindui = function() {
    $("#tslider").slider({
        range:true, min:0, max:this.plxinfo.length, values:[0, this.plxinfo.length],
        slide: function(event, ui) {
            $("#tstart").val(BMI.hms(ui.values[0]));
            $("#tend").val(BMI.hms(ui.values[1]));
        },
    });
    $("#tstart").val(BMI.hms(0));
    $("#tend").val(BMI.hms(this.plxinfo.length));
    $("#tstart").keyup(function(e) {
        var values = $("#tslider").slider("values");
        var sec = BMI.ptime(this.value);
        if (sec !== null) {
            $("#tslider").slider("values", [sec, values[1]]);
        }
        if (e.which == 13)
            this.value = BMI.hms(sec);
    });
    $("#tend").keyup(function(e) {
        var values = $("#tslider").slider("values");
        var sec = BMI.ptime(this.value);
        if (sec !== null) {
            $("#tslider").slider("values", [values[0], sec]);
        }
        if (e.which == 13)
            this.value = BMI.hms(sec);
    });
    $("#tstart").blur(function() {
        var values = $("#tslider").slider("values");
        this.value = BMI.hms(values[0]);
    });
    $("#tend").blur(function() {
        var values = $("#tslider").slider("values");
        this.value = BMI.hms(values[1]);
    });

    $('#makecell').click(function() {
        var units = $('#available option:selected');
        units.each(function(idx, obj) {
            this.add($(obj).text());
        }.bind(this));
        this.update();
    }.bind(this));

    $('#makeavail').click(function() {
        var units = $('#cells option:selected');
        units.each(function(idx, obj) {
            this.remove($(obj).text());
        }.bind(this));
        this.update();
    }.bind(this));

    $("#cellnames").blur(function(e) {
        this.parse($("#cellnames").val());
    }.bind(this));

    $("#bmitrain").click(this.train.bind(this));
    $("#bmicancel").click(this.cancel.bind(this));
    $("#bmi").show();
}
BMI.prototype.destroy = function() {
    if (this.plxinfo !== null) {
        $("#tslider").slider("destroy");
        $("#tstart").unbind("keyup");
        $("#tstart").unbind("blur");
        $("#tend").unbind("keyup");
        $("#tend").unbind("blur");
        $("#makecell").unbind("click");
        $("#makeavail").unbind("click");
        $("#cellnames").unbind("click");
        $("#cellnames").unbind("blur");
        $("#bmitrain").unbind("click");
        $("#bmicancel").unbind("click");
        $("#bmi").hide();
    }
}

BMI.prototype.train = function() {
    this.update();
    var csrf = $("#experiment input[name=csrfmiddlewaretoken]");
    var data = {};
    data.bminame = $("#bminame").val();
    data.bmiclass = $("#bmiclass").val();
    data.cells = $("#cellnames").val();
    data.binlen = $("#bmibinlen").val();
    data.tslice = $("#tslider").slider("values");
    data.csrfmiddlewaretoken = csrf.val();

    $.post("/make_bmi/"+this.idx, data, function(resp) {
        if (resp.status == "success") {
            alert("BMI Training queued");
            this.cancel();
        } else
            alert(resp.msg);
    }.bind(this), "json");
}