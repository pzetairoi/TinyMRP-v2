import{r as Ie,j as Ze}from"./index-IEvuyt3L.js";/**
 * @license
 * Copyright 2010-2025 Three.js Authors
 * SPDX-License-Identifier: MIT
 */const wo="179",Ci={ROTATE:0,DOLLY:1,PAN:2},Ai={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},zl=0,qo=1,Hl=2,nl=1,kl=2,Tn=3,Vn=0,Wt=1,An=2,Hn=0,Pi=1,Yo=2,jo=3,Ko=4,Vl=5,Qn=100,Gl=101,Wl=102,Xl=103,ql=104,Yl=200,jl=201,Kl=202,Zl=203,Bs=204,zs=205,$l=206,Jl=207,Ql=208,ec=209,tc=210,nc=211,ic=212,rc=213,sc=214,Hs=0,ks=1,Vs=2,Ui=3,Gs=4,Ws=5,Xs=6,qs=7,Ro=0,oc=1,ac=2,kn=0,lc=1,cc=2,uc=3,hc=4,dc=5,fc=6,pc=7,il=300,Ii=301,Ni=302,Ys=303,js=304,jr=306,ti=1e3,wn=1001,Qi=1002,Zt=1003,mc=1004,ur=1005,Gt=1006,es=1007,Rn=1008,_n=1009,rl=1010,sl=1011,er=1012,Co=1013,ni=1014,Cn=1015,or=1016,Po=1017,Do=1018,tr=1020,ol=35902,al=1021,ll=1022,dn=1023,nr=1026,ir=1027,cl=1028,Lo=1029,ul=1030,Uo=1031,Io=1033,Br=33776,zr=33777,Hr=33778,kr=33779,Ks=35840,Zs=35841,$s=35842,Js=35843,Qs=36196,eo=37492,to=37496,no=37808,io=37809,ro=37810,so=37811,oo=37812,ao=37813,lo=37814,co=37815,uo=37816,ho=37817,fo=37818,po=37819,mo=37820,go=37821,Vr=36492,_o=36494,vo=36495,hl=36283,xo=36284,Mo=36285,So=36286,gc=3200,_c=3201,No=0,vc=1,Bn="",Dt="srgb",Fi="srgb-linear",Wr="linear",ht="srgb",hi=7680,Zo=519,xc=512,Mc=513,Sc=514,dl=515,yc=516,Ec=517,Tc=518,bc=519,$o=35044,Jo="300 es",gn=2e3,Xr=2001;class si{addEventListener(e,t){this._listeners===void 0&&(this._listeners={});const n=this._listeners;n[e]===void 0&&(n[e]=[]),n[e].indexOf(t)===-1&&n[e].push(t)}hasEventListener(e,t){const n=this._listeners;return n===void 0?!1:n[e]!==void 0&&n[e].indexOf(t)!==-1}removeEventListener(e,t){const n=this._listeners;if(n===void 0)return;const r=n[e];if(r!==void 0){const s=r.indexOf(t);s!==-1&&r.splice(s,1)}}dispatchEvent(e){const t=this._listeners;if(t===void 0)return;const n=t[e.type];if(n!==void 0){e.target=this;const r=n.slice(0);for(let s=0,o=r.length;s<o;s++)r[s].call(this,e);e.target=null}}}const Lt=["00","01","02","03","04","05","06","07","08","09","0a","0b","0c","0d","0e","0f","10","11","12","13","14","15","16","17","18","19","1a","1b","1c","1d","1e","1f","20","21","22","23","24","25","26","27","28","29","2a","2b","2c","2d","2e","2f","30","31","32","33","34","35","36","37","38","39","3a","3b","3c","3d","3e","3f","40","41","42","43","44","45","46","47","48","49","4a","4b","4c","4d","4e","4f","50","51","52","53","54","55","56","57","58","59","5a","5b","5c","5d","5e","5f","60","61","62","63","64","65","66","67","68","69","6a","6b","6c","6d","6e","6f","70","71","72","73","74","75","76","77","78","79","7a","7b","7c","7d","7e","7f","80","81","82","83","84","85","86","87","88","89","8a","8b","8c","8d","8e","8f","90","91","92","93","94","95","96","97","98","99","9a","9b","9c","9d","9e","9f","a0","a1","a2","a3","a4","a5","a6","a7","a8","a9","aa","ab","ac","ad","ae","af","b0","b1","b2","b3","b4","b5","b6","b7","b8","b9","ba","bb","bc","bd","be","bf","c0","c1","c2","c3","c4","c5","c6","c7","c8","c9","ca","cb","cc","cd","ce","cf","d0","d1","d2","d3","d4","d5","d6","d7","d8","d9","da","db","dc","dd","de","df","e0","e1","e2","e3","e4","e5","e6","e7","e8","e9","ea","eb","ec","ed","ee","ef","f0","f1","f2","f3","f4","f5","f6","f7","f8","f9","fa","fb","fc","fd","fe","ff"],Zi=Math.PI/180,yo=180/Math.PI;function ar(){const i=Math.random()*4294967295|0,e=Math.random()*4294967295|0,t=Math.random()*4294967295|0,n=Math.random()*4294967295|0;return(Lt[i&255]+Lt[i>>8&255]+Lt[i>>16&255]+Lt[i>>24&255]+"-"+Lt[e&255]+Lt[e>>8&255]+"-"+Lt[e>>16&15|64]+Lt[e>>24&255]+"-"+Lt[t&63|128]+Lt[t>>8&255]+"-"+Lt[t>>16&255]+Lt[t>>24&255]+Lt[n&255]+Lt[n>>8&255]+Lt[n>>16&255]+Lt[n>>24&255]).toLowerCase()}function rt(i,e,t){return Math.max(e,Math.min(t,i))}function Ac(i,e){return(i%e+e)%e}function ts(i,e,t){return(1-t)*i+t*e}function Gi(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return i/4294967295;case Uint16Array:return i/65535;case Uint8Array:return i/255;case Int32Array:return Math.max(i/2147483647,-1);case Int16Array:return Math.max(i/32767,-1);case Int8Array:return Math.max(i/127,-1);default:throw new Error("Invalid component type.")}}function Ht(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return Math.round(i*4294967295);case Uint16Array:return Math.round(i*65535);case Uint8Array:return Math.round(i*255);case Int32Array:return Math.round(i*2147483647);case Int16Array:return Math.round(i*32767);case Int8Array:return Math.round(i*127);default:throw new Error("Invalid component type.")}}const wc={DEG2RAD:Zi};class Ye{constructor(e=0,t=0){Ye.prototype.isVector2=!0,this.x=e,this.y=t}get width(){return this.x}set width(e){this.x=e}get height(){return this.y}set height(e){this.y=e}set(e,t){return this.x=e,this.y=t,this}setScalar(e){return this.x=e,this.y=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y)}copy(e){return this.x=e.x,this.y=e.y,this}add(e){return this.x+=e.x,this.y+=e.y,this}addScalar(e){return this.x+=e,this.y+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this}subScalar(e){return this.x-=e,this.y-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this}multiply(e){return this.x*=e.x,this.y*=e.y,this}multiplyScalar(e){return this.x*=e,this.y*=e,this}divide(e){return this.x/=e.x,this.y/=e.y,this}divideScalar(e){return this.multiplyScalar(1/e)}applyMatrix3(e){const t=this.x,n=this.y,r=e.elements;return this.x=r[0]*t+r[3]*n+r[6],this.y=r[1]*t+r[4]*n+r[7],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this}clamp(e,t){return this.x=rt(this.x,e.x,t.x),this.y=rt(this.y,e.y,t.y),this}clampScalar(e,t){return this.x=rt(this.x,e,t),this.y=rt(this.y,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(rt(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(e){return this.x*e.x+this.y*e.y}cross(e){return this.x*e.y-this.y*e.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(e){const t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;const n=this.dot(e)/t;return Math.acos(rt(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){const t=this.x-e.x,n=this.y-e.y;return t*t+n*n}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this}equals(e){return e.x===this.x&&e.y===this.y}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this}rotateAround(e,t){const n=Math.cos(t),r=Math.sin(t),s=this.x-e.x,o=this.y-e.y;return this.x=s*n-o*r+e.x,this.y=s*r+o*n+e.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}}class ii{constructor(e=0,t=0,n=0,r=1){this.isQuaternion=!0,this._x=e,this._y=t,this._z=n,this._w=r}static slerpFlat(e,t,n,r,s,o,a){let u=n[r+0],l=n[r+1],d=n[r+2],h=n[r+3];const f=s[o+0],m=s[o+1],_=s[o+2],v=s[o+3];if(a===0){e[t+0]=u,e[t+1]=l,e[t+2]=d,e[t+3]=h;return}if(a===1){e[t+0]=f,e[t+1]=m,e[t+2]=_,e[t+3]=v;return}if(h!==v||u!==f||l!==m||d!==_){let p=1-a;const c=u*f+l*m+d*_+h*v,A=c>=0?1:-1,S=1-c*c;if(S>Number.EPSILON){const C=Math.sqrt(S),R=Math.atan2(C,c*A);p=Math.sin(p*R)/C,a=Math.sin(a*R)/C}const M=a*A;if(u=u*p+f*M,l=l*p+m*M,d=d*p+_*M,h=h*p+v*M,p===1-a){const C=1/Math.sqrt(u*u+l*l+d*d+h*h);u*=C,l*=C,d*=C,h*=C}}e[t]=u,e[t+1]=l,e[t+2]=d,e[t+3]=h}static multiplyQuaternionsFlat(e,t,n,r,s,o){const a=n[r],u=n[r+1],l=n[r+2],d=n[r+3],h=s[o],f=s[o+1],m=s[o+2],_=s[o+3];return e[t]=a*_+d*h+u*m-l*f,e[t+1]=u*_+d*f+l*h-a*m,e[t+2]=l*_+d*m+a*f-u*h,e[t+3]=d*_-a*h-u*f-l*m,e}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get w(){return this._w}set w(e){this._w=e,this._onChangeCallback()}set(e,t,n,r){return this._x=e,this._y=t,this._z=n,this._w=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(e){return this._x=e.x,this._y=e.y,this._z=e.z,this._w=e.w,this._onChangeCallback(),this}setFromEuler(e,t=!0){const n=e._x,r=e._y,s=e._z,o=e._order,a=Math.cos,u=Math.sin,l=a(n/2),d=a(r/2),h=a(s/2),f=u(n/2),m=u(r/2),_=u(s/2);switch(o){case"XYZ":this._x=f*d*h+l*m*_,this._y=l*m*h-f*d*_,this._z=l*d*_+f*m*h,this._w=l*d*h-f*m*_;break;case"YXZ":this._x=f*d*h+l*m*_,this._y=l*m*h-f*d*_,this._z=l*d*_-f*m*h,this._w=l*d*h+f*m*_;break;case"ZXY":this._x=f*d*h-l*m*_,this._y=l*m*h+f*d*_,this._z=l*d*_+f*m*h,this._w=l*d*h-f*m*_;break;case"ZYX":this._x=f*d*h-l*m*_,this._y=l*m*h+f*d*_,this._z=l*d*_-f*m*h,this._w=l*d*h+f*m*_;break;case"YZX":this._x=f*d*h+l*m*_,this._y=l*m*h+f*d*_,this._z=l*d*_-f*m*h,this._w=l*d*h-f*m*_;break;case"XZY":this._x=f*d*h-l*m*_,this._y=l*m*h-f*d*_,this._z=l*d*_+f*m*h,this._w=l*d*h+f*m*_;break;default:console.warn("THREE.Quaternion: .setFromEuler() encountered an unknown order: "+o)}return t===!0&&this._onChangeCallback(),this}setFromAxisAngle(e,t){const n=t/2,r=Math.sin(n);return this._x=e.x*r,this._y=e.y*r,this._z=e.z*r,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(e){const t=e.elements,n=t[0],r=t[4],s=t[8],o=t[1],a=t[5],u=t[9],l=t[2],d=t[6],h=t[10],f=n+a+h;if(f>0){const m=.5/Math.sqrt(f+1);this._w=.25/m,this._x=(d-u)*m,this._y=(s-l)*m,this._z=(o-r)*m}else if(n>a&&n>h){const m=2*Math.sqrt(1+n-a-h);this._w=(d-u)/m,this._x=.25*m,this._y=(r+o)/m,this._z=(s+l)/m}else if(a>h){const m=2*Math.sqrt(1+a-n-h);this._w=(s-l)/m,this._x=(r+o)/m,this._y=.25*m,this._z=(u+d)/m}else{const m=2*Math.sqrt(1+h-n-a);this._w=(o-r)/m,this._x=(s+l)/m,this._y=(u+d)/m,this._z=.25*m}return this._onChangeCallback(),this}setFromUnitVectors(e,t){let n=e.dot(t)+1;return n<1e-8?(n=0,Math.abs(e.x)>Math.abs(e.z)?(this._x=-e.y,this._y=e.x,this._z=0,this._w=n):(this._x=0,this._y=-e.z,this._z=e.y,this._w=n)):(this._x=e.y*t.z-e.z*t.y,this._y=e.z*t.x-e.x*t.z,this._z=e.x*t.y-e.y*t.x,this._w=n),this.normalize()}angleTo(e){return 2*Math.acos(Math.abs(rt(this.dot(e),-1,1)))}rotateTowards(e,t){const n=this.angleTo(e);if(n===0)return this;const r=Math.min(1,t/n);return this.slerp(e,r),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(e){return this._x*e._x+this._y*e._y+this._z*e._z+this._w*e._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let e=this.length();return e===0?(this._x=0,this._y=0,this._z=0,this._w=1):(e=1/e,this._x=this._x*e,this._y=this._y*e,this._z=this._z*e,this._w=this._w*e),this._onChangeCallback(),this}multiply(e){return this.multiplyQuaternions(this,e)}premultiply(e){return this.multiplyQuaternions(e,this)}multiplyQuaternions(e,t){const n=e._x,r=e._y,s=e._z,o=e._w,a=t._x,u=t._y,l=t._z,d=t._w;return this._x=n*d+o*a+r*l-s*u,this._y=r*d+o*u+s*a-n*l,this._z=s*d+o*l+n*u-r*a,this._w=o*d-n*a-r*u-s*l,this._onChangeCallback(),this}slerp(e,t){if(t===0)return this;if(t===1)return this.copy(e);const n=this._x,r=this._y,s=this._z,o=this._w;let a=o*e._w+n*e._x+r*e._y+s*e._z;if(a<0?(this._w=-e._w,this._x=-e._x,this._y=-e._y,this._z=-e._z,a=-a):this.copy(e),a>=1)return this._w=o,this._x=n,this._y=r,this._z=s,this;const u=1-a*a;if(u<=Number.EPSILON){const m=1-t;return this._w=m*o+t*this._w,this._x=m*n+t*this._x,this._y=m*r+t*this._y,this._z=m*s+t*this._z,this.normalize(),this}const l=Math.sqrt(u),d=Math.atan2(l,a),h=Math.sin((1-t)*d)/l,f=Math.sin(t*d)/l;return this._w=o*h+this._w*f,this._x=n*h+this._x*f,this._y=r*h+this._y*f,this._z=s*h+this._z*f,this._onChangeCallback(),this}slerpQuaternions(e,t,n){return this.copy(e).slerp(t,n)}random(){const e=2*Math.PI*Math.random(),t=2*Math.PI*Math.random(),n=Math.random(),r=Math.sqrt(1-n),s=Math.sqrt(n);return this.set(r*Math.sin(e),r*Math.cos(e),s*Math.sin(t),s*Math.cos(t))}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._w===this._w}fromArray(e,t=0){return this._x=e[t],this._y=e[t+1],this._z=e[t+2],this._w=e[t+3],this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._w,e}fromBufferAttribute(e,t){return this._x=e.getX(t),this._y=e.getY(t),this._z=e.getZ(t),this._w=e.getW(t),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}}class B{constructor(e=0,t=0,n=0){B.prototype.isVector3=!0,this.x=e,this.y=t,this.z=n}set(e,t,n){return n===void 0&&(n=this.z),this.x=e,this.y=t,this.z=n,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this}multiplyVectors(e,t){return this.x=e.x*t.x,this.y=e.y*t.y,this.z=e.z*t.z,this}applyEuler(e){return this.applyQuaternion(Qo.setFromEuler(e))}applyAxisAngle(e,t){return this.applyQuaternion(Qo.setFromAxisAngle(e,t))}applyMatrix3(e){const t=this.x,n=this.y,r=this.z,s=e.elements;return this.x=s[0]*t+s[3]*n+s[6]*r,this.y=s[1]*t+s[4]*n+s[7]*r,this.z=s[2]*t+s[5]*n+s[8]*r,this}applyNormalMatrix(e){return this.applyMatrix3(e).normalize()}applyMatrix4(e){const t=this.x,n=this.y,r=this.z,s=e.elements,o=1/(s[3]*t+s[7]*n+s[11]*r+s[15]);return this.x=(s[0]*t+s[4]*n+s[8]*r+s[12])*o,this.y=(s[1]*t+s[5]*n+s[9]*r+s[13])*o,this.z=(s[2]*t+s[6]*n+s[10]*r+s[14])*o,this}applyQuaternion(e){const t=this.x,n=this.y,r=this.z,s=e.x,o=e.y,a=e.z,u=e.w,l=2*(o*r-a*n),d=2*(a*t-s*r),h=2*(s*n-o*t);return this.x=t+u*l+o*h-a*d,this.y=n+u*d+a*l-s*h,this.z=r+u*h+s*d-o*l,this}project(e){return this.applyMatrix4(e.matrixWorldInverse).applyMatrix4(e.projectionMatrix)}unproject(e){return this.applyMatrix4(e.projectionMatrixInverse).applyMatrix4(e.matrixWorld)}transformDirection(e){const t=this.x,n=this.y,r=this.z,s=e.elements;return this.x=s[0]*t+s[4]*n+s[8]*r,this.y=s[1]*t+s[5]*n+s[9]*r,this.z=s[2]*t+s[6]*n+s[10]*r,this.normalize()}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this}divideScalar(e){return this.multiplyScalar(1/e)}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this}clamp(e,t){return this.x=rt(this.x,e.x,t.x),this.y=rt(this.y,e.y,t.y),this.z=rt(this.z,e.z,t.z),this}clampScalar(e,t){return this.x=rt(this.x,e,t),this.y=rt(this.y,e,t),this.z=rt(this.z,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(rt(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this}cross(e){return this.crossVectors(this,e)}crossVectors(e,t){const n=e.x,r=e.y,s=e.z,o=t.x,a=t.y,u=t.z;return this.x=r*u-s*a,this.y=s*o-n*u,this.z=n*a-r*o,this}projectOnVector(e){const t=e.lengthSq();if(t===0)return this.set(0,0,0);const n=e.dot(this)/t;return this.copy(e).multiplyScalar(n)}projectOnPlane(e){return ns.copy(this).projectOnVector(e),this.sub(ns)}reflect(e){return this.sub(ns.copy(e).multiplyScalar(2*this.dot(e)))}angleTo(e){const t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;const n=this.dot(e)/t;return Math.acos(rt(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){const t=this.x-e.x,n=this.y-e.y,r=this.z-e.z;return t*t+n*n+r*r}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)+Math.abs(this.z-e.z)}setFromSpherical(e){return this.setFromSphericalCoords(e.radius,e.phi,e.theta)}setFromSphericalCoords(e,t,n){const r=Math.sin(t)*e;return this.x=r*Math.sin(n),this.y=Math.cos(t)*e,this.z=r*Math.cos(n),this}setFromCylindrical(e){return this.setFromCylindricalCoords(e.radius,e.theta,e.y)}setFromCylindricalCoords(e,t,n){return this.x=e*Math.sin(t),this.y=n,this.z=e*Math.cos(t),this}setFromMatrixPosition(e){const t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this}setFromMatrixScale(e){const t=this.setFromMatrixColumn(e,0).length(),n=this.setFromMatrixColumn(e,1).length(),r=this.setFromMatrixColumn(e,2).length();return this.x=t,this.y=n,this.z=r,this}setFromMatrixColumn(e,t){return this.fromArray(e.elements,t*4)}setFromMatrix3Column(e,t){return this.fromArray(e.elements,t*3)}setFromEuler(e){return this.x=e._x,this.y=e._y,this.z=e._z,this}setFromColor(e){return this.x=e.r,this.y=e.g,this.z=e.b,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){const e=Math.random()*Math.PI*2,t=Math.random()*2-1,n=Math.sqrt(1-t*t);return this.x=n*Math.cos(e),this.y=t,this.z=n*Math.sin(e),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}}const ns=new B,Qo=new ii;class Qe{constructor(e,t,n,r,s,o,a,u,l){Qe.prototype.isMatrix3=!0,this.elements=[1,0,0,0,1,0,0,0,1],e!==void 0&&this.set(e,t,n,r,s,o,a,u,l)}set(e,t,n,r,s,o,a,u,l){const d=this.elements;return d[0]=e,d[1]=r,d[2]=a,d[3]=t,d[4]=s,d[5]=u,d[6]=n,d[7]=o,d[8]=l,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(e){const t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],this}extractBasis(e,t,n){return e.setFromMatrix3Column(this,0),t.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(e){const t=e.elements;return this.set(t[0],t[4],t[8],t[1],t[5],t[9],t[2],t[6],t[10]),this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){const n=e.elements,r=t.elements,s=this.elements,o=n[0],a=n[3],u=n[6],l=n[1],d=n[4],h=n[7],f=n[2],m=n[5],_=n[8],v=r[0],p=r[3],c=r[6],A=r[1],S=r[4],M=r[7],C=r[2],R=r[5],P=r[8];return s[0]=o*v+a*A+u*C,s[3]=o*p+a*S+u*R,s[6]=o*c+a*M+u*P,s[1]=l*v+d*A+h*C,s[4]=l*p+d*S+h*R,s[7]=l*c+d*M+h*P,s[2]=f*v+m*A+_*C,s[5]=f*p+m*S+_*R,s[8]=f*c+m*M+_*P,this}multiplyScalar(e){const t=this.elements;return t[0]*=e,t[3]*=e,t[6]*=e,t[1]*=e,t[4]*=e,t[7]*=e,t[2]*=e,t[5]*=e,t[8]*=e,this}determinant(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],o=e[4],a=e[5],u=e[6],l=e[7],d=e[8];return t*o*d-t*a*l-n*s*d+n*a*u+r*s*l-r*o*u}invert(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],o=e[4],a=e[5],u=e[6],l=e[7],d=e[8],h=d*o-a*l,f=a*u-d*s,m=l*s-o*u,_=t*h+n*f+r*m;if(_===0)return this.set(0,0,0,0,0,0,0,0,0);const v=1/_;return e[0]=h*v,e[1]=(r*l-d*n)*v,e[2]=(a*n-r*o)*v,e[3]=f*v,e[4]=(d*t-r*u)*v,e[5]=(r*s-a*t)*v,e[6]=m*v,e[7]=(n*u-l*t)*v,e[8]=(o*t-n*s)*v,this}transpose(){let e;const t=this.elements;return e=t[1],t[1]=t[3],t[3]=e,e=t[2],t[2]=t[6],t[6]=e,e=t[5],t[5]=t[7],t[7]=e,this}getNormalMatrix(e){return this.setFromMatrix4(e).invert().transpose()}transposeIntoArray(e){const t=this.elements;return e[0]=t[0],e[1]=t[3],e[2]=t[6],e[3]=t[1],e[4]=t[4],e[5]=t[7],e[6]=t[2],e[7]=t[5],e[8]=t[8],this}setUvTransform(e,t,n,r,s,o,a){const u=Math.cos(s),l=Math.sin(s);return this.set(n*u,n*l,-n*(u*o+l*a)+o+e,-r*l,r*u,-r*(-l*o+u*a)+a+t,0,0,1),this}scale(e,t){return this.premultiply(is.makeScale(e,t)),this}rotate(e){return this.premultiply(is.makeRotation(-e)),this}translate(e,t){return this.premultiply(is.makeTranslation(e,t)),this}makeTranslation(e,t){return e.isVector2?this.set(1,0,e.x,0,1,e.y,0,0,1):this.set(1,0,e,0,1,t,0,0,1),this}makeRotation(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,n,t,0,0,0,1),this}makeScale(e,t){return this.set(e,0,0,0,t,0,0,0,1),this}equals(e){const t=this.elements,n=e.elements;for(let r=0;r<9;r++)if(t[r]!==n[r])return!1;return!0}fromArray(e,t=0){for(let n=0;n<9;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){const n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e}clone(){return new this.constructor().fromArray(this.elements)}}const is=new Qe;function fl(i){for(let e=i.length-1;e>=0;--e)if(i[e]>=65535)return!0;return!1}function rr(i){return document.createElementNS("http://www.w3.org/1999/xhtml",i)}function Rc(){const i=rr("canvas");return i.style.display="block",i}const ea={};function Di(i){i in ea||(ea[i]=!0,console.warn(i))}function Cc(i,e,t){return new Promise(function(n,r){function s(){switch(i.clientWaitSync(e,i.SYNC_FLUSH_COMMANDS_BIT,0)){case i.WAIT_FAILED:r();break;case i.TIMEOUT_EXPIRED:setTimeout(s,t);break;default:n()}}setTimeout(s,t)})}const ta=new Qe().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),na=new Qe().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);function Pc(){const i={enabled:!0,workingColorSpace:Fi,spaces:{},convert:function(r,s,o){return this.enabled===!1||s===o||!s||!o||(this.spaces[s].transfer===ht&&(r.r=Pn(r.r),r.g=Pn(r.g),r.b=Pn(r.b)),this.spaces[s].primaries!==this.spaces[o].primaries&&(r.applyMatrix3(this.spaces[s].toXYZ),r.applyMatrix3(this.spaces[o].fromXYZ)),this.spaces[o].transfer===ht&&(r.r=Li(r.r),r.g=Li(r.g),r.b=Li(r.b))),r},workingToColorSpace:function(r,s){return this.convert(r,this.workingColorSpace,s)},colorSpaceToWorking:function(r,s){return this.convert(r,s,this.workingColorSpace)},getPrimaries:function(r){return this.spaces[r].primaries},getTransfer:function(r){return r===Bn?Wr:this.spaces[r].transfer},getLuminanceCoefficients:function(r,s=this.workingColorSpace){return r.fromArray(this.spaces[s].luminanceCoefficients)},define:function(r){Object.assign(this.spaces,r)},_getMatrix:function(r,s,o){return r.copy(this.spaces[s].toXYZ).multiply(this.spaces[o].fromXYZ)},_getDrawingBufferColorSpace:function(r){return this.spaces[r].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(r=this.workingColorSpace){return this.spaces[r].workingColorSpaceConfig.unpackColorSpace},fromWorkingColorSpace:function(r,s){return Di("THREE.ColorManagement: .fromWorkingColorSpace() has been renamed to .workingToColorSpace()."),i.workingToColorSpace(r,s)},toWorkingColorSpace:function(r,s){return Di("THREE.ColorManagement: .toWorkingColorSpace() has been renamed to .colorSpaceToWorking()."),i.colorSpaceToWorking(r,s)}},e=[.64,.33,.3,.6,.15,.06],t=[.2126,.7152,.0722],n=[.3127,.329];return i.define({[Fi]:{primaries:e,whitePoint:n,transfer:Wr,toXYZ:ta,fromXYZ:na,luminanceCoefficients:t,workingColorSpaceConfig:{unpackColorSpace:Dt},outputColorSpaceConfig:{drawingBufferColorSpace:Dt}},[Dt]:{primaries:e,whitePoint:n,transfer:ht,toXYZ:ta,fromXYZ:na,luminanceCoefficients:t,outputColorSpaceConfig:{drawingBufferColorSpace:Dt}}}),i}const at=Pc();function Pn(i){return i<.04045?i*.0773993808:Math.pow(i*.9478672986+.0521327014,2.4)}function Li(i){return i<.0031308?i*12.92:1.055*Math.pow(i,.41666)-.055}let di;class Dc{static getDataURL(e,t="image/png"){if(/^data:/i.test(e.src)||typeof HTMLCanvasElement>"u")return e.src;let n;if(e instanceof HTMLCanvasElement)n=e;else{di===void 0&&(di=rr("canvas")),di.width=e.width,di.height=e.height;const r=di.getContext("2d");e instanceof ImageData?r.putImageData(e,0,0):r.drawImage(e,0,0,e.width,e.height),n=di}return n.toDataURL(t)}static sRGBToLinear(e){if(typeof HTMLImageElement<"u"&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&e instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&e instanceof ImageBitmap){const t=rr("canvas");t.width=e.width,t.height=e.height;const n=t.getContext("2d");n.drawImage(e,0,0,e.width,e.height);const r=n.getImageData(0,0,e.width,e.height),s=r.data;for(let o=0;o<s.length;o++)s[o]=Pn(s[o]/255)*255;return n.putImageData(r,0,0),t}else if(e.data){const t=e.data.slice(0);for(let n=0;n<t.length;n++)t instanceof Uint8Array||t instanceof Uint8ClampedArray?t[n]=Math.floor(Pn(t[n]/255)*255):t[n]=Pn(t[n]);return{data:t,width:e.width,height:e.height}}else return console.warn("THREE.ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied."),e}}let Lc=0;class Fo{constructor(e=null){this.isSource=!0,Object.defineProperty(this,"id",{value:Lc++}),this.uuid=ar(),this.data=e,this.dataReady=!0,this.version=0}getSize(e){const t=this.data;return t instanceof HTMLVideoElement?e.set(t.videoWidth,t.videoHeight,0):t instanceof VideoFrame?e.set(t.displayHeight,t.displayWidth,0):t!==null?e.set(t.width,t.height,t.depth||0):e.set(0,0,0),e}set needsUpdate(e){e===!0&&this.version++}toJSON(e){const t=e===void 0||typeof e=="string";if(!t&&e.images[this.uuid]!==void 0)return e.images[this.uuid];const n={uuid:this.uuid,url:""},r=this.data;if(r!==null){let s;if(Array.isArray(r)){s=[];for(let o=0,a=r.length;o<a;o++)r[o].isDataTexture?s.push(rs(r[o].image)):s.push(rs(r[o]))}else s=rs(r);n.url=s}return t||(e.images[this.uuid]=n),n}}function rs(i){return typeof HTMLImageElement<"u"&&i instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&i instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&i instanceof ImageBitmap?Dc.getDataURL(i):i.data?{data:Array.from(i.data),width:i.width,height:i.height,type:i.data.constructor.name}:(console.warn("THREE.Texture: Unable to serialize Texture."),{})}let Uc=0;const ss=new B;class Ot extends si{constructor(e=Ot.DEFAULT_IMAGE,t=Ot.DEFAULT_MAPPING,n=wn,r=wn,s=Gt,o=Rn,a=dn,u=_n,l=Ot.DEFAULT_ANISOTROPY,d=Bn){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:Uc++}),this.uuid=ar(),this.name="",this.source=new Fo(e),this.mipmaps=[],this.mapping=t,this.channel=0,this.wrapS=n,this.wrapT=r,this.magFilter=s,this.minFilter=o,this.anisotropy=l,this.format=a,this.internalFormat=null,this.type=u,this.offset=new Ye(0,0),this.repeat=new Ye(1,1),this.center=new Ye(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new Qe,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=d,this.userData={},this.updateRanges=[],this.version=0,this.onUpdate=null,this.renderTarget=null,this.isRenderTargetTexture=!1,this.isArrayTexture=!!(e&&e.depth&&e.depth>1),this.pmremVersion=0}get width(){return this.source.getSize(ss).x}get height(){return this.source.getSize(ss).y}get depth(){return this.source.getSize(ss).z}get image(){return this.source.data}set image(e=null){this.source.data=e}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}clone(){return new this.constructor().copy(this)}copy(e){return this.name=e.name,this.source=e.source,this.mipmaps=e.mipmaps.slice(0),this.mapping=e.mapping,this.channel=e.channel,this.wrapS=e.wrapS,this.wrapT=e.wrapT,this.magFilter=e.magFilter,this.minFilter=e.minFilter,this.anisotropy=e.anisotropy,this.format=e.format,this.internalFormat=e.internalFormat,this.type=e.type,this.offset.copy(e.offset),this.repeat.copy(e.repeat),this.center.copy(e.center),this.rotation=e.rotation,this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrix.copy(e.matrix),this.generateMipmaps=e.generateMipmaps,this.premultiplyAlpha=e.premultiplyAlpha,this.flipY=e.flipY,this.unpackAlignment=e.unpackAlignment,this.colorSpace=e.colorSpace,this.renderTarget=e.renderTarget,this.isRenderTargetTexture=e.isRenderTargetTexture,this.isArrayTexture=e.isArrayTexture,this.userData=JSON.parse(JSON.stringify(e.userData)),this.needsUpdate=!0,this}setValues(e){for(const t in e){const n=e[t];if(n===void 0){console.warn(`THREE.Texture.setValues(): parameter '${t}' has value of undefined.`);continue}const r=this[t];if(r===void 0){console.warn(`THREE.Texture.setValues(): property '${t}' does not exist.`);continue}r&&n&&r.isVector2&&n.isVector2||r&&n&&r.isVector3&&n.isVector3||r&&n&&r.isMatrix3&&n.isMatrix3?r.copy(n):this[t]=n}}toJSON(e){const t=e===void 0||typeof e=="string";if(!t&&e.textures[this.uuid]!==void 0)return e.textures[this.uuid];const n={metadata:{version:4.7,type:"Texture",generator:"Texture.toJSON"},uuid:this.uuid,name:this.name,image:this.source.toJSON(e).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),t||(e.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:"dispose"})}transformUv(e){if(this.mapping!==il)return e;if(e.applyMatrix3(this.matrix),e.x<0||e.x>1)switch(this.wrapS){case ti:e.x=e.x-Math.floor(e.x);break;case wn:e.x=e.x<0?0:1;break;case Qi:Math.abs(Math.floor(e.x)%2)===1?e.x=Math.ceil(e.x)-e.x:e.x=e.x-Math.floor(e.x);break}if(e.y<0||e.y>1)switch(this.wrapT){case ti:e.y=e.y-Math.floor(e.y);break;case wn:e.y=e.y<0?0:1;break;case Qi:Math.abs(Math.floor(e.y)%2)===1?e.y=Math.ceil(e.y)-e.y:e.y=e.y-Math.floor(e.y);break}return this.flipY&&(e.y=1-e.y),e}set needsUpdate(e){e===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(e){e===!0&&this.pmremVersion++}}Ot.DEFAULT_IMAGE=null;Ot.DEFAULT_MAPPING=il;Ot.DEFAULT_ANISOTROPY=1;class Mt{constructor(e=0,t=0,n=0,r=1){Mt.prototype.isVector4=!0,this.x=e,this.y=t,this.z=n,this.w=r}get width(){return this.z}set width(e){this.z=e}get height(){return this.w}set height(e){this.w=e}set(e,t,n,r){return this.x=e,this.y=t,this.z=n,this.w=r,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this.w=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setW(e){return this.w=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;case 3:this.w=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this.w=e.w!==void 0?e.w:1,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this.w+=e.w,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this.w+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this.w=e.w+t.w,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this.w+=e.w*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this.w-=e.w,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this.w-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this.w=e.w-t.w,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this.w*=e.w,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this.w*=e,this}applyMatrix4(e){const t=this.x,n=this.y,r=this.z,s=this.w,o=e.elements;return this.x=o[0]*t+o[4]*n+o[8]*r+o[12]*s,this.y=o[1]*t+o[5]*n+o[9]*r+o[13]*s,this.z=o[2]*t+o[6]*n+o[10]*r+o[14]*s,this.w=o[3]*t+o[7]*n+o[11]*r+o[15]*s,this}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this.w/=e.w,this}divideScalar(e){return this.multiplyScalar(1/e)}setAxisAngleFromQuaternion(e){this.w=2*Math.acos(e.w);const t=Math.sqrt(1-e.w*e.w);return t<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=e.x/t,this.y=e.y/t,this.z=e.z/t),this}setAxisAngleFromRotationMatrix(e){let t,n,r,s;const u=e.elements,l=u[0],d=u[4],h=u[8],f=u[1],m=u[5],_=u[9],v=u[2],p=u[6],c=u[10];if(Math.abs(d-f)<.01&&Math.abs(h-v)<.01&&Math.abs(_-p)<.01){if(Math.abs(d+f)<.1&&Math.abs(h+v)<.1&&Math.abs(_+p)<.1&&Math.abs(l+m+c-3)<.1)return this.set(1,0,0,0),this;t=Math.PI;const S=(l+1)/2,M=(m+1)/2,C=(c+1)/2,R=(d+f)/4,P=(h+v)/4,I=(_+p)/4;return S>M&&S>C?S<.01?(n=0,r=.707106781,s=.707106781):(n=Math.sqrt(S),r=R/n,s=P/n):M>C?M<.01?(n=.707106781,r=0,s=.707106781):(r=Math.sqrt(M),n=R/r,s=I/r):C<.01?(n=.707106781,r=.707106781,s=0):(s=Math.sqrt(C),n=P/s,r=I/s),this.set(n,r,s,t),this}let A=Math.sqrt((p-_)*(p-_)+(h-v)*(h-v)+(f-d)*(f-d));return Math.abs(A)<.001&&(A=1),this.x=(p-_)/A,this.y=(h-v)/A,this.z=(f-d)/A,this.w=Math.acos((l+m+c-1)/2),this}setFromMatrixPosition(e){const t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this.w=t[15],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this.w=Math.min(this.w,e.w),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this.w=Math.max(this.w,e.w),this}clamp(e,t){return this.x=rt(this.x,e.x,t.x),this.y=rt(this.y,e.y,t.y),this.z=rt(this.z,e.z,t.z),this.w=rt(this.w,e.w,t.w),this}clampScalar(e,t){return this.x=rt(this.x,e,t),this.y=rt(this.y,e,t),this.z=rt(this.z,e,t),this.w=rt(this.w,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(rt(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z+this.w*e.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this.w+=(e.w-this.w)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this.w=e.w+(t.w-e.w)*n,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z&&e.w===this.w}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this.w=e[t+3],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e[t+3]=this.w,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this.w=e.getW(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}}class Ic extends si{constructor(e=1,t=1,n={}){super(),n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:Gt,depthBuffer:!0,stencilBuffer:!1,resolveDepthBuffer:!0,resolveStencilBuffer:!0,depthTexture:null,samples:0,count:1,depth:1,multiview:!1},n),this.isRenderTarget=!0,this.width=e,this.height=t,this.depth=n.depth,this.scissor=new Mt(0,0,e,t),this.scissorTest=!1,this.viewport=new Mt(0,0,e,t);const r={width:e,height:t,depth:n.depth},s=new Ot(r);this.textures=[];const o=n.count;for(let a=0;a<o;a++)this.textures[a]=s.clone(),this.textures[a].isRenderTargetTexture=!0,this.textures[a].renderTarget=this;this._setTextureOptions(n),this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this._depthTexture=null,this.depthTexture=n.depthTexture,this.samples=n.samples,this.multiview=n.multiview}_setTextureOptions(e={}){const t={minFilter:Gt,generateMipmaps:!1,flipY:!1,internalFormat:null};e.mapping!==void 0&&(t.mapping=e.mapping),e.wrapS!==void 0&&(t.wrapS=e.wrapS),e.wrapT!==void 0&&(t.wrapT=e.wrapT),e.wrapR!==void 0&&(t.wrapR=e.wrapR),e.magFilter!==void 0&&(t.magFilter=e.magFilter),e.minFilter!==void 0&&(t.minFilter=e.minFilter),e.format!==void 0&&(t.format=e.format),e.type!==void 0&&(t.type=e.type),e.anisotropy!==void 0&&(t.anisotropy=e.anisotropy),e.colorSpace!==void 0&&(t.colorSpace=e.colorSpace),e.flipY!==void 0&&(t.flipY=e.flipY),e.generateMipmaps!==void 0&&(t.generateMipmaps=e.generateMipmaps),e.internalFormat!==void 0&&(t.internalFormat=e.internalFormat);for(let n=0;n<this.textures.length;n++)this.textures[n].setValues(t)}get texture(){return this.textures[0]}set texture(e){this.textures[0]=e}set depthTexture(e){this._depthTexture!==null&&(this._depthTexture.renderTarget=null),e!==null&&(e.renderTarget=this),this._depthTexture=e}get depthTexture(){return this._depthTexture}setSize(e,t,n=1){if(this.width!==e||this.height!==t||this.depth!==n){this.width=e,this.height=t,this.depth=n;for(let r=0,s=this.textures.length;r<s;r++)this.textures[r].image.width=e,this.textures[r].image.height=t,this.textures[r].image.depth=n,this.textures[r].isArrayTexture=this.textures[r].image.depth>1;this.dispose()}this.viewport.set(0,0,e,t),this.scissor.set(0,0,e,t)}clone(){return new this.constructor().copy(this)}copy(e){this.width=e.width,this.height=e.height,this.depth=e.depth,this.scissor.copy(e.scissor),this.scissorTest=e.scissorTest,this.viewport.copy(e.viewport),this.textures.length=0;for(let t=0,n=e.textures.length;t<n;t++){this.textures[t]=e.textures[t].clone(),this.textures[t].isRenderTargetTexture=!0,this.textures[t].renderTarget=this;const r=Object.assign({},e.textures[t].image);this.textures[t].source=new Fo(r)}return this.depthBuffer=e.depthBuffer,this.stencilBuffer=e.stencilBuffer,this.resolveDepthBuffer=e.resolveDepthBuffer,this.resolveStencilBuffer=e.resolveStencilBuffer,e.depthTexture!==null&&(this.depthTexture=e.depthTexture.clone()),this.samples=e.samples,this}dispose(){this.dispatchEvent({type:"dispose"})}}class ri extends Ic{constructor(e=1,t=1,n={}){super(e,t,n),this.isWebGLRenderTarget=!0}}class pl extends Ot{constructor(e=null,t=1,n=1,r=1){super(null),this.isDataArrayTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=Zt,this.minFilter=Zt,this.wrapR=wn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}addLayerUpdate(e){this.layerUpdates.add(e)}clearLayerUpdates(){this.layerUpdates.clear()}}class Nc extends Ot{constructor(e=null,t=1,n=1,r=1){super(null),this.isData3DTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=Zt,this.minFilter=Zt,this.wrapR=wn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}}class Bi{constructor(e=new B(1/0,1/0,1/0),t=new B(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=e,this.max=t}set(e,t){return this.min.copy(e),this.max.copy(t),this}setFromArray(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t+=3)this.expandByPoint(an.fromArray(e,t));return this}setFromBufferAttribute(e){this.makeEmpty();for(let t=0,n=e.count;t<n;t++)this.expandByPoint(an.fromBufferAttribute(e,t));return this}setFromPoints(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t++)this.expandByPoint(e[t]);return this}setFromCenterAndSize(e,t){const n=an.copy(t).multiplyScalar(.5);return this.min.copy(e).sub(n),this.max.copy(e).add(n),this}setFromObject(e,t=!1){return this.makeEmpty(),this.expandByObject(e,t)}clone(){return new this.constructor().copy(this)}copy(e){return this.min.copy(e.min),this.max.copy(e.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(e){return this.isEmpty()?e.set(0,0,0):e.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(e){return this.isEmpty()?e.set(0,0,0):e.subVectors(this.max,this.min)}expandByPoint(e){return this.min.min(e),this.max.max(e),this}expandByVector(e){return this.min.sub(e),this.max.add(e),this}expandByScalar(e){return this.min.addScalar(-e),this.max.addScalar(e),this}expandByObject(e,t=!1){e.updateWorldMatrix(!1,!1);const n=e.geometry;if(n!==void 0){const s=n.getAttribute("position");if(t===!0&&s!==void 0&&e.isInstancedMesh!==!0)for(let o=0,a=s.count;o<a;o++)e.isMesh===!0?e.getVertexPosition(o,an):an.fromBufferAttribute(s,o),an.applyMatrix4(e.matrixWorld),this.expandByPoint(an);else e.boundingBox!==void 0?(e.boundingBox===null&&e.computeBoundingBox(),hr.copy(e.boundingBox)):(n.boundingBox===null&&n.computeBoundingBox(),hr.copy(n.boundingBox)),hr.applyMatrix4(e.matrixWorld),this.union(hr)}const r=e.children;for(let s=0,o=r.length;s<o;s++)this.expandByObject(r[s],t);return this}containsPoint(e){return e.x>=this.min.x&&e.x<=this.max.x&&e.y>=this.min.y&&e.y<=this.max.y&&e.z>=this.min.z&&e.z<=this.max.z}containsBox(e){return this.min.x<=e.min.x&&e.max.x<=this.max.x&&this.min.y<=e.min.y&&e.max.y<=this.max.y&&this.min.z<=e.min.z&&e.max.z<=this.max.z}getParameter(e,t){return t.set((e.x-this.min.x)/(this.max.x-this.min.x),(e.y-this.min.y)/(this.max.y-this.min.y),(e.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(e){return e.max.x>=this.min.x&&e.min.x<=this.max.x&&e.max.y>=this.min.y&&e.min.y<=this.max.y&&e.max.z>=this.min.z&&e.min.z<=this.max.z}intersectsSphere(e){return this.clampPoint(e.center,an),an.distanceToSquared(e.center)<=e.radius*e.radius}intersectsPlane(e){let t,n;return e.normal.x>0?(t=e.normal.x*this.min.x,n=e.normal.x*this.max.x):(t=e.normal.x*this.max.x,n=e.normal.x*this.min.x),e.normal.y>0?(t+=e.normal.y*this.min.y,n+=e.normal.y*this.max.y):(t+=e.normal.y*this.max.y,n+=e.normal.y*this.min.y),e.normal.z>0?(t+=e.normal.z*this.min.z,n+=e.normal.z*this.max.z):(t+=e.normal.z*this.max.z,n+=e.normal.z*this.min.z),t<=-e.constant&&n>=-e.constant}intersectsTriangle(e){if(this.isEmpty())return!1;this.getCenter(Wi),dr.subVectors(this.max,Wi),fi.subVectors(e.a,Wi),pi.subVectors(e.b,Wi),mi.subVectors(e.c,Wi),Dn.subVectors(pi,fi),Ln.subVectors(mi,pi),qn.subVectors(fi,mi);let t=[0,-Dn.z,Dn.y,0,-Ln.z,Ln.y,0,-qn.z,qn.y,Dn.z,0,-Dn.x,Ln.z,0,-Ln.x,qn.z,0,-qn.x,-Dn.y,Dn.x,0,-Ln.y,Ln.x,0,-qn.y,qn.x,0];return!os(t,fi,pi,mi,dr)||(t=[1,0,0,0,1,0,0,0,1],!os(t,fi,pi,mi,dr))?!1:(fr.crossVectors(Dn,Ln),t=[fr.x,fr.y,fr.z],os(t,fi,pi,mi,dr))}clampPoint(e,t){return t.copy(e).clamp(this.min,this.max)}distanceToPoint(e){return this.clampPoint(e,an).distanceTo(e)}getBoundingSphere(e){return this.isEmpty()?e.makeEmpty():(this.getCenter(e.center),e.radius=this.getSize(an).length()*.5),e}intersect(e){return this.min.max(e.min),this.max.min(e.max),this.isEmpty()&&this.makeEmpty(),this}union(e){return this.min.min(e.min),this.max.max(e.max),this}applyMatrix4(e){return this.isEmpty()?this:(vn[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(e),vn[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(e),vn[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(e),vn[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(e),vn[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(e),vn[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(e),vn[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(e),vn[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(e),this.setFromPoints(vn),this)}translate(e){return this.min.add(e),this.max.add(e),this}equals(e){return e.min.equals(this.min)&&e.max.equals(this.max)}toJSON(){return{min:this.min.toArray(),max:this.max.toArray()}}fromJSON(e){return this.min.fromArray(e.min),this.max.fromArray(e.max),this}}const vn=[new B,new B,new B,new B,new B,new B,new B,new B],an=new B,hr=new Bi,fi=new B,pi=new B,mi=new B,Dn=new B,Ln=new B,qn=new B,Wi=new B,dr=new B,fr=new B,Yn=new B;function os(i,e,t,n,r){for(let s=0,o=i.length-3;s<=o;s+=3){Yn.fromArray(i,s);const a=r.x*Math.abs(Yn.x)+r.y*Math.abs(Yn.y)+r.z*Math.abs(Yn.z),u=e.dot(Yn),l=t.dot(Yn),d=n.dot(Yn);if(Math.max(-Math.max(u,l,d),Math.min(u,l,d))>a)return!1}return!0}const Fc=new Bi,Xi=new B,as=new B;class Kr{constructor(e=new B,t=-1){this.isSphere=!0,this.center=e,this.radius=t}set(e,t){return this.center.copy(e),this.radius=t,this}setFromPoints(e,t){const n=this.center;t!==void 0?n.copy(t):Fc.setFromPoints(e).getCenter(n);let r=0;for(let s=0,o=e.length;s<o;s++)r=Math.max(r,n.distanceToSquared(e[s]));return this.radius=Math.sqrt(r),this}copy(e){return this.center.copy(e.center),this.radius=e.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(e){return e.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(e){return e.distanceTo(this.center)-this.radius}intersectsSphere(e){const t=this.radius+e.radius;return e.center.distanceToSquared(this.center)<=t*t}intersectsBox(e){return e.intersectsSphere(this)}intersectsPlane(e){return Math.abs(e.distanceToPoint(this.center))<=this.radius}clampPoint(e,t){const n=this.center.distanceToSquared(e);return t.copy(e),n>this.radius*this.radius&&(t.sub(this.center).normalize(),t.multiplyScalar(this.radius).add(this.center)),t}getBoundingBox(e){return this.isEmpty()?(e.makeEmpty(),e):(e.set(this.center,this.center),e.expandByScalar(this.radius),e)}applyMatrix4(e){return this.center.applyMatrix4(e),this.radius=this.radius*e.getMaxScaleOnAxis(),this}translate(e){return this.center.add(e),this}expandByPoint(e){if(this.isEmpty())return this.center.copy(e),this.radius=0,this;Xi.subVectors(e,this.center);const t=Xi.lengthSq();if(t>this.radius*this.radius){const n=Math.sqrt(t),r=(n-this.radius)*.5;this.center.addScaledVector(Xi,r/n),this.radius+=r}return this}union(e){return e.isEmpty()?this:this.isEmpty()?(this.copy(e),this):(this.center.equals(e.center)===!0?this.radius=Math.max(this.radius,e.radius):(as.subVectors(e.center,this.center).setLength(e.radius),this.expandByPoint(Xi.copy(e.center).add(as)),this.expandByPoint(Xi.copy(e.center).sub(as))),this)}equals(e){return e.center.equals(this.center)&&e.radius===this.radius}clone(){return new this.constructor().copy(this)}toJSON(){return{radius:this.radius,center:this.center.toArray()}}fromJSON(e){return this.radius=e.radius,this.center.fromArray(e.center),this}}const xn=new B,ls=new B,pr=new B,Un=new B,cs=new B,mr=new B,us=new B;class Zr{constructor(e=new B,t=new B(0,0,-1)){this.origin=e,this.direction=t}set(e,t){return this.origin.copy(e),this.direction.copy(t),this}copy(e){return this.origin.copy(e.origin),this.direction.copy(e.direction),this}at(e,t){return t.copy(this.origin).addScaledVector(this.direction,e)}lookAt(e){return this.direction.copy(e).sub(this.origin).normalize(),this}recast(e){return this.origin.copy(this.at(e,xn)),this}closestPointToPoint(e,t){t.subVectors(e,this.origin);const n=t.dot(this.direction);return n<0?t.copy(this.origin):t.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(e){return Math.sqrt(this.distanceSqToPoint(e))}distanceSqToPoint(e){const t=xn.subVectors(e,this.origin).dot(this.direction);return t<0?this.origin.distanceToSquared(e):(xn.copy(this.origin).addScaledVector(this.direction,t),xn.distanceToSquared(e))}distanceSqToSegment(e,t,n,r){ls.copy(e).add(t).multiplyScalar(.5),pr.copy(t).sub(e).normalize(),Un.copy(this.origin).sub(ls);const s=e.distanceTo(t)*.5,o=-this.direction.dot(pr),a=Un.dot(this.direction),u=-Un.dot(pr),l=Un.lengthSq(),d=Math.abs(1-o*o);let h,f,m,_;if(d>0)if(h=o*u-a,f=o*a-u,_=s*d,h>=0)if(f>=-_)if(f<=_){const v=1/d;h*=v,f*=v,m=h*(h+o*f+2*a)+f*(o*h+f+2*u)+l}else f=s,h=Math.max(0,-(o*f+a)),m=-h*h+f*(f+2*u)+l;else f=-s,h=Math.max(0,-(o*f+a)),m=-h*h+f*(f+2*u)+l;else f<=-_?(h=Math.max(0,-(-o*s+a)),f=h>0?-s:Math.min(Math.max(-s,-u),s),m=-h*h+f*(f+2*u)+l):f<=_?(h=0,f=Math.min(Math.max(-s,-u),s),m=f*(f+2*u)+l):(h=Math.max(0,-(o*s+a)),f=h>0?s:Math.min(Math.max(-s,-u),s),m=-h*h+f*(f+2*u)+l);else f=o>0?-s:s,h=Math.max(0,-(o*f+a)),m=-h*h+f*(f+2*u)+l;return n&&n.copy(this.origin).addScaledVector(this.direction,h),r&&r.copy(ls).addScaledVector(pr,f),m}intersectSphere(e,t){xn.subVectors(e.center,this.origin);const n=xn.dot(this.direction),r=xn.dot(xn)-n*n,s=e.radius*e.radius;if(r>s)return null;const o=Math.sqrt(s-r),a=n-o,u=n+o;return u<0?null:a<0?this.at(u,t):this.at(a,t)}intersectsSphere(e){return e.radius<0?!1:this.distanceSqToPoint(e.center)<=e.radius*e.radius}distanceToPlane(e){const t=e.normal.dot(this.direction);if(t===0)return e.distanceToPoint(this.origin)===0?0:null;const n=-(this.origin.dot(e.normal)+e.constant)/t;return n>=0?n:null}intersectPlane(e,t){const n=this.distanceToPlane(e);return n===null?null:this.at(n,t)}intersectsPlane(e){const t=e.distanceToPoint(this.origin);return t===0||e.normal.dot(this.direction)*t<0}intersectBox(e,t){let n,r,s,o,a,u;const l=1/this.direction.x,d=1/this.direction.y,h=1/this.direction.z,f=this.origin;return l>=0?(n=(e.min.x-f.x)*l,r=(e.max.x-f.x)*l):(n=(e.max.x-f.x)*l,r=(e.min.x-f.x)*l),d>=0?(s=(e.min.y-f.y)*d,o=(e.max.y-f.y)*d):(s=(e.max.y-f.y)*d,o=(e.min.y-f.y)*d),n>o||s>r||((s>n||isNaN(n))&&(n=s),(o<r||isNaN(r))&&(r=o),h>=0?(a=(e.min.z-f.z)*h,u=(e.max.z-f.z)*h):(a=(e.max.z-f.z)*h,u=(e.min.z-f.z)*h),n>u||a>r)||((a>n||n!==n)&&(n=a),(u<r||r!==r)&&(r=u),r<0)?null:this.at(n>=0?n:r,t)}intersectsBox(e){return this.intersectBox(e,xn)!==null}intersectTriangle(e,t,n,r,s){cs.subVectors(t,e),mr.subVectors(n,e),us.crossVectors(cs,mr);let o=this.direction.dot(us),a;if(o>0){if(r)return null;a=1}else if(o<0)a=-1,o=-o;else return null;Un.subVectors(this.origin,e);const u=a*this.direction.dot(mr.crossVectors(Un,mr));if(u<0)return null;const l=a*this.direction.dot(cs.cross(Un));if(l<0||u+l>o)return null;const d=-a*Un.dot(us);return d<0?null:this.at(d/o,s)}applyMatrix4(e){return this.origin.applyMatrix4(e),this.direction.transformDirection(e),this}equals(e){return e.origin.equals(this.origin)&&e.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}}class gt{constructor(e,t,n,r,s,o,a,u,l,d,h,f,m,_,v,p){gt.prototype.isMatrix4=!0,this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],e!==void 0&&this.set(e,t,n,r,s,o,a,u,l,d,h,f,m,_,v,p)}set(e,t,n,r,s,o,a,u,l,d,h,f,m,_,v,p){const c=this.elements;return c[0]=e,c[4]=t,c[8]=n,c[12]=r,c[1]=s,c[5]=o,c[9]=a,c[13]=u,c[2]=l,c[6]=d,c[10]=h,c[14]=f,c[3]=m,c[7]=_,c[11]=v,c[15]=p,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new gt().fromArray(this.elements)}copy(e){const t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],t[9]=n[9],t[10]=n[10],t[11]=n[11],t[12]=n[12],t[13]=n[13],t[14]=n[14],t[15]=n[15],this}copyPosition(e){const t=this.elements,n=e.elements;return t[12]=n[12],t[13]=n[13],t[14]=n[14],this}setFromMatrix3(e){const t=e.elements;return this.set(t[0],t[3],t[6],0,t[1],t[4],t[7],0,t[2],t[5],t[8],0,0,0,0,1),this}extractBasis(e,t,n){return e.setFromMatrixColumn(this,0),t.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this}makeBasis(e,t,n){return this.set(e.x,t.x,n.x,0,e.y,t.y,n.y,0,e.z,t.z,n.z,0,0,0,0,1),this}extractRotation(e){const t=this.elements,n=e.elements,r=1/gi.setFromMatrixColumn(e,0).length(),s=1/gi.setFromMatrixColumn(e,1).length(),o=1/gi.setFromMatrixColumn(e,2).length();return t[0]=n[0]*r,t[1]=n[1]*r,t[2]=n[2]*r,t[3]=0,t[4]=n[4]*s,t[5]=n[5]*s,t[6]=n[6]*s,t[7]=0,t[8]=n[8]*o,t[9]=n[9]*o,t[10]=n[10]*o,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromEuler(e){const t=this.elements,n=e.x,r=e.y,s=e.z,o=Math.cos(n),a=Math.sin(n),u=Math.cos(r),l=Math.sin(r),d=Math.cos(s),h=Math.sin(s);if(e.order==="XYZ"){const f=o*d,m=o*h,_=a*d,v=a*h;t[0]=u*d,t[4]=-u*h,t[8]=l,t[1]=m+_*l,t[5]=f-v*l,t[9]=-a*u,t[2]=v-f*l,t[6]=_+m*l,t[10]=o*u}else if(e.order==="YXZ"){const f=u*d,m=u*h,_=l*d,v=l*h;t[0]=f+v*a,t[4]=_*a-m,t[8]=o*l,t[1]=o*h,t[5]=o*d,t[9]=-a,t[2]=m*a-_,t[6]=v+f*a,t[10]=o*u}else if(e.order==="ZXY"){const f=u*d,m=u*h,_=l*d,v=l*h;t[0]=f-v*a,t[4]=-o*h,t[8]=_+m*a,t[1]=m+_*a,t[5]=o*d,t[9]=v-f*a,t[2]=-o*l,t[6]=a,t[10]=o*u}else if(e.order==="ZYX"){const f=o*d,m=o*h,_=a*d,v=a*h;t[0]=u*d,t[4]=_*l-m,t[8]=f*l+v,t[1]=u*h,t[5]=v*l+f,t[9]=m*l-_,t[2]=-l,t[6]=a*u,t[10]=o*u}else if(e.order==="YZX"){const f=o*u,m=o*l,_=a*u,v=a*l;t[0]=u*d,t[4]=v-f*h,t[8]=_*h+m,t[1]=h,t[5]=o*d,t[9]=-a*d,t[2]=-l*d,t[6]=m*h+_,t[10]=f-v*h}else if(e.order==="XZY"){const f=o*u,m=o*l,_=a*u,v=a*l;t[0]=u*d,t[4]=-h,t[8]=l*d,t[1]=f*h+v,t[5]=o*d,t[9]=m*h-_,t[2]=_*h-m,t[6]=a*d,t[10]=v*h+f}return t[3]=0,t[7]=0,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromQuaternion(e){return this.compose(Oc,e,Bc)}lookAt(e,t,n){const r=this.elements;return Yt.subVectors(e,t),Yt.lengthSq()===0&&(Yt.z=1),Yt.normalize(),In.crossVectors(n,Yt),In.lengthSq()===0&&(Math.abs(n.z)===1?Yt.x+=1e-4:Yt.z+=1e-4,Yt.normalize(),In.crossVectors(n,Yt)),In.normalize(),gr.crossVectors(Yt,In),r[0]=In.x,r[4]=gr.x,r[8]=Yt.x,r[1]=In.y,r[5]=gr.y,r[9]=Yt.y,r[2]=In.z,r[6]=gr.z,r[10]=Yt.z,this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){const n=e.elements,r=t.elements,s=this.elements,o=n[0],a=n[4],u=n[8],l=n[12],d=n[1],h=n[5],f=n[9],m=n[13],_=n[2],v=n[6],p=n[10],c=n[14],A=n[3],S=n[7],M=n[11],C=n[15],R=r[0],P=r[4],I=r[8],y=r[12],E=r[1],w=r[5],Q=r[9],j=r[13],Z=r[2],re=r[6],X=r[10],ae=r[14],W=r[3],he=r[7],ye=r[11],Te=r[15];return s[0]=o*R+a*E+u*Z+l*W,s[4]=o*P+a*w+u*re+l*he,s[8]=o*I+a*Q+u*X+l*ye,s[12]=o*y+a*j+u*ae+l*Te,s[1]=d*R+h*E+f*Z+m*W,s[5]=d*P+h*w+f*re+m*he,s[9]=d*I+h*Q+f*X+m*ye,s[13]=d*y+h*j+f*ae+m*Te,s[2]=_*R+v*E+p*Z+c*W,s[6]=_*P+v*w+p*re+c*he,s[10]=_*I+v*Q+p*X+c*ye,s[14]=_*y+v*j+p*ae+c*Te,s[3]=A*R+S*E+M*Z+C*W,s[7]=A*P+S*w+M*re+C*he,s[11]=A*I+S*Q+M*X+C*ye,s[15]=A*y+S*j+M*ae+C*Te,this}multiplyScalar(e){const t=this.elements;return t[0]*=e,t[4]*=e,t[8]*=e,t[12]*=e,t[1]*=e,t[5]*=e,t[9]*=e,t[13]*=e,t[2]*=e,t[6]*=e,t[10]*=e,t[14]*=e,t[3]*=e,t[7]*=e,t[11]*=e,t[15]*=e,this}determinant(){const e=this.elements,t=e[0],n=e[4],r=e[8],s=e[12],o=e[1],a=e[5],u=e[9],l=e[13],d=e[2],h=e[6],f=e[10],m=e[14],_=e[3],v=e[7],p=e[11],c=e[15];return _*(+s*u*h-r*l*h-s*a*f+n*l*f+r*a*m-n*u*m)+v*(+t*u*m-t*l*f+s*o*f-r*o*m+r*l*d-s*u*d)+p*(+t*l*h-t*a*m-s*o*h+n*o*m+s*a*d-n*l*d)+c*(-r*a*d-t*u*h+t*a*f+r*o*h-n*o*f+n*u*d)}transpose(){const e=this.elements;let t;return t=e[1],e[1]=e[4],e[4]=t,t=e[2],e[2]=e[8],e[8]=t,t=e[6],e[6]=e[9],e[9]=t,t=e[3],e[3]=e[12],e[12]=t,t=e[7],e[7]=e[13],e[13]=t,t=e[11],e[11]=e[14],e[14]=t,this}setPosition(e,t,n){const r=this.elements;return e.isVector3?(r[12]=e.x,r[13]=e.y,r[14]=e.z):(r[12]=e,r[13]=t,r[14]=n),this}invert(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],o=e[4],a=e[5],u=e[6],l=e[7],d=e[8],h=e[9],f=e[10],m=e[11],_=e[12],v=e[13],p=e[14],c=e[15],A=h*p*l-v*f*l+v*u*m-a*p*m-h*u*c+a*f*c,S=_*f*l-d*p*l-_*u*m+o*p*m+d*u*c-o*f*c,M=d*v*l-_*h*l+_*a*m-o*v*m-d*a*c+o*h*c,C=_*h*u-d*v*u-_*a*f+o*v*f+d*a*p-o*h*p,R=t*A+n*S+r*M+s*C;if(R===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);const P=1/R;return e[0]=A*P,e[1]=(v*f*s-h*p*s-v*r*m+n*p*m+h*r*c-n*f*c)*P,e[2]=(a*p*s-v*u*s+v*r*l-n*p*l-a*r*c+n*u*c)*P,e[3]=(h*u*s-a*f*s-h*r*l+n*f*l+a*r*m-n*u*m)*P,e[4]=S*P,e[5]=(d*p*s-_*f*s+_*r*m-t*p*m-d*r*c+t*f*c)*P,e[6]=(_*u*s-o*p*s-_*r*l+t*p*l+o*r*c-t*u*c)*P,e[7]=(o*f*s-d*u*s+d*r*l-t*f*l-o*r*m+t*u*m)*P,e[8]=M*P,e[9]=(_*h*s-d*v*s-_*n*m+t*v*m+d*n*c-t*h*c)*P,e[10]=(o*v*s-_*a*s+_*n*l-t*v*l-o*n*c+t*a*c)*P,e[11]=(d*a*s-o*h*s-d*n*l+t*h*l+o*n*m-t*a*m)*P,e[12]=C*P,e[13]=(d*v*r-_*h*r+_*n*f-t*v*f-d*n*p+t*h*p)*P,e[14]=(_*a*r-o*v*r-_*n*u+t*v*u+o*n*p-t*a*p)*P,e[15]=(o*h*r-d*a*r+d*n*u-t*h*u-o*n*f+t*a*f)*P,this}scale(e){const t=this.elements,n=e.x,r=e.y,s=e.z;return t[0]*=n,t[4]*=r,t[8]*=s,t[1]*=n,t[5]*=r,t[9]*=s,t[2]*=n,t[6]*=r,t[10]*=s,t[3]*=n,t[7]*=r,t[11]*=s,this}getMaxScaleOnAxis(){const e=this.elements,t=e[0]*e[0]+e[1]*e[1]+e[2]*e[2],n=e[4]*e[4]+e[5]*e[5]+e[6]*e[6],r=e[8]*e[8]+e[9]*e[9]+e[10]*e[10];return Math.sqrt(Math.max(t,n,r))}makeTranslation(e,t,n){return e.isVector3?this.set(1,0,0,e.x,0,1,0,e.y,0,0,1,e.z,0,0,0,1):this.set(1,0,0,e,0,1,0,t,0,0,1,n,0,0,0,1),this}makeRotationX(e){const t=Math.cos(e),n=Math.sin(e);return this.set(1,0,0,0,0,t,-n,0,0,n,t,0,0,0,0,1),this}makeRotationY(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,0,n,0,0,1,0,0,-n,0,t,0,0,0,0,1),this}makeRotationZ(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,0,n,t,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(e,t){const n=Math.cos(t),r=Math.sin(t),s=1-n,o=e.x,a=e.y,u=e.z,l=s*o,d=s*a;return this.set(l*o+n,l*a-r*u,l*u+r*a,0,l*a+r*u,d*a+n,d*u-r*o,0,l*u-r*a,d*u+r*o,s*u*u+n,0,0,0,0,1),this}makeScale(e,t,n){return this.set(e,0,0,0,0,t,0,0,0,0,n,0,0,0,0,1),this}makeShear(e,t,n,r,s,o){return this.set(1,n,s,0,e,1,o,0,t,r,1,0,0,0,0,1),this}compose(e,t,n){const r=this.elements,s=t._x,o=t._y,a=t._z,u=t._w,l=s+s,d=o+o,h=a+a,f=s*l,m=s*d,_=s*h,v=o*d,p=o*h,c=a*h,A=u*l,S=u*d,M=u*h,C=n.x,R=n.y,P=n.z;return r[0]=(1-(v+c))*C,r[1]=(m+M)*C,r[2]=(_-S)*C,r[3]=0,r[4]=(m-M)*R,r[5]=(1-(f+c))*R,r[6]=(p+A)*R,r[7]=0,r[8]=(_+S)*P,r[9]=(p-A)*P,r[10]=(1-(f+v))*P,r[11]=0,r[12]=e.x,r[13]=e.y,r[14]=e.z,r[15]=1,this}decompose(e,t,n){const r=this.elements;let s=gi.set(r[0],r[1],r[2]).length();const o=gi.set(r[4],r[5],r[6]).length(),a=gi.set(r[8],r[9],r[10]).length();this.determinant()<0&&(s=-s),e.x=r[12],e.y=r[13],e.z=r[14],ln.copy(this);const l=1/s,d=1/o,h=1/a;return ln.elements[0]*=l,ln.elements[1]*=l,ln.elements[2]*=l,ln.elements[4]*=d,ln.elements[5]*=d,ln.elements[6]*=d,ln.elements[8]*=h,ln.elements[9]*=h,ln.elements[10]*=h,t.setFromRotationMatrix(ln),n.x=s,n.y=o,n.z=a,this}makePerspective(e,t,n,r,s,o,a=gn,u=!1){const l=this.elements,d=2*s/(t-e),h=2*s/(n-r),f=(t+e)/(t-e),m=(n+r)/(n-r);let _,v;if(u)_=s/(o-s),v=o*s/(o-s);else if(a===gn)_=-(o+s)/(o-s),v=-2*o*s/(o-s);else if(a===Xr)_=-o/(o-s),v=-o*s/(o-s);else throw new Error("THREE.Matrix4.makePerspective(): Invalid coordinate system: "+a);return l[0]=d,l[4]=0,l[8]=f,l[12]=0,l[1]=0,l[5]=h,l[9]=m,l[13]=0,l[2]=0,l[6]=0,l[10]=_,l[14]=v,l[3]=0,l[7]=0,l[11]=-1,l[15]=0,this}makeOrthographic(e,t,n,r,s,o,a=gn,u=!1){const l=this.elements,d=2/(t-e),h=2/(n-r),f=-(t+e)/(t-e),m=-(n+r)/(n-r);let _,v;if(u)_=1/(o-s),v=o/(o-s);else if(a===gn)_=-2/(o-s),v=-(o+s)/(o-s);else if(a===Xr)_=-1/(o-s),v=-s/(o-s);else throw new Error("THREE.Matrix4.makeOrthographic(): Invalid coordinate system: "+a);return l[0]=d,l[4]=0,l[8]=0,l[12]=f,l[1]=0,l[5]=h,l[9]=0,l[13]=m,l[2]=0,l[6]=0,l[10]=_,l[14]=v,l[3]=0,l[7]=0,l[11]=0,l[15]=1,this}equals(e){const t=this.elements,n=e.elements;for(let r=0;r<16;r++)if(t[r]!==n[r])return!1;return!0}fromArray(e,t=0){for(let n=0;n<16;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){const n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e[t+9]=n[9],e[t+10]=n[10],e[t+11]=n[11],e[t+12]=n[12],e[t+13]=n[13],e[t+14]=n[14],e[t+15]=n[15],e}}const gi=new B,ln=new gt,Oc=new B(0,0,0),Bc=new B(1,1,1),In=new B,gr=new B,Yt=new B,ia=new gt,ra=new ii;class fn{constructor(e=0,t=0,n=0,r=fn.DEFAULT_ORDER){this.isEuler=!0,this._x=e,this._y=t,this._z=n,this._order=r}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get order(){return this._order}set order(e){this._order=e,this._onChangeCallback()}set(e,t,n,r=this._order){return this._x=e,this._y=t,this._z=n,this._order=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(e){return this._x=e._x,this._y=e._y,this._z=e._z,this._order=e._order,this._onChangeCallback(),this}setFromRotationMatrix(e,t=this._order,n=!0){const r=e.elements,s=r[0],o=r[4],a=r[8],u=r[1],l=r[5],d=r[9],h=r[2],f=r[6],m=r[10];switch(t){case"XYZ":this._y=Math.asin(rt(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(-d,m),this._z=Math.atan2(-o,s)):(this._x=Math.atan2(f,l),this._z=0);break;case"YXZ":this._x=Math.asin(-rt(d,-1,1)),Math.abs(d)<.9999999?(this._y=Math.atan2(a,m),this._z=Math.atan2(u,l)):(this._y=Math.atan2(-h,s),this._z=0);break;case"ZXY":this._x=Math.asin(rt(f,-1,1)),Math.abs(f)<.9999999?(this._y=Math.atan2(-h,m),this._z=Math.atan2(-o,l)):(this._y=0,this._z=Math.atan2(u,s));break;case"ZYX":this._y=Math.asin(-rt(h,-1,1)),Math.abs(h)<.9999999?(this._x=Math.atan2(f,m),this._z=Math.atan2(u,s)):(this._x=0,this._z=Math.atan2(-o,l));break;case"YZX":this._z=Math.asin(rt(u,-1,1)),Math.abs(u)<.9999999?(this._x=Math.atan2(-d,l),this._y=Math.atan2(-h,s)):(this._x=0,this._y=Math.atan2(a,m));break;case"XZY":this._z=Math.asin(-rt(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(f,l),this._y=Math.atan2(a,s)):(this._x=Math.atan2(-d,m),this._y=0);break;default:console.warn("THREE.Euler: .setFromRotationMatrix() encountered an unknown order: "+t)}return this._order=t,n===!0&&this._onChangeCallback(),this}setFromQuaternion(e,t,n){return ia.makeRotationFromQuaternion(e),this.setFromRotationMatrix(ia,t,n)}setFromVector3(e,t=this._order){return this.set(e.x,e.y,e.z,t)}reorder(e){return ra.setFromEuler(this),this.setFromQuaternion(ra,e)}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._order===this._order}fromArray(e){return this._x=e[0],this._y=e[1],this._z=e[2],e[3]!==void 0&&(this._order=e[3]),this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._order,e}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}}fn.DEFAULT_ORDER="XYZ";class Oo{constructor(){this.mask=1}set(e){this.mask=(1<<e|0)>>>0}enable(e){this.mask|=1<<e|0}enableAll(){this.mask=-1}toggle(e){this.mask^=1<<e|0}disable(e){this.mask&=~(1<<e|0)}disableAll(){this.mask=0}test(e){return(this.mask&e.mask)!==0}isEnabled(e){return(this.mask&(1<<e|0))!==0}}let zc=0;const sa=new B,_i=new ii,Mn=new gt,_r=new B,qi=new B,Hc=new B,kc=new ii,oa=new B(1,0,0),aa=new B(0,1,0),la=new B(0,0,1),ca={type:"added"},Vc={type:"removed"},vi={type:"childadded",child:null},hs={type:"childremoved",child:null};class Pt extends si{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:zc++}),this.uuid=ar(),this.name="",this.type="Object3D",this.parent=null,this.children=[],this.up=Pt.DEFAULT_UP.clone();const e=new B,t=new fn,n=new ii,r=new B(1,1,1);function s(){n.setFromEuler(t,!1)}function o(){t.setFromQuaternion(n,void 0,!1)}t._onChange(s),n._onChange(o),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:e},rotation:{configurable:!0,enumerable:!0,value:t},quaternion:{configurable:!0,enumerable:!0,value:n},scale:{configurable:!0,enumerable:!0,value:r},modelViewMatrix:{value:new gt},normalMatrix:{value:new Qe}}),this.matrix=new gt,this.matrixWorld=new gt,this.matrixAutoUpdate=Pt.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=Pt.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new Oo,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.customDepthMaterial=void 0,this.customDistanceMaterial=void 0,this.userData={}}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(e){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(e),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(e){return this.quaternion.premultiply(e),this}setRotationFromAxisAngle(e,t){this.quaternion.setFromAxisAngle(e,t)}setRotationFromEuler(e){this.quaternion.setFromEuler(e,!0)}setRotationFromMatrix(e){this.quaternion.setFromRotationMatrix(e)}setRotationFromQuaternion(e){this.quaternion.copy(e)}rotateOnAxis(e,t){return _i.setFromAxisAngle(e,t),this.quaternion.multiply(_i),this}rotateOnWorldAxis(e,t){return _i.setFromAxisAngle(e,t),this.quaternion.premultiply(_i),this}rotateX(e){return this.rotateOnAxis(oa,e)}rotateY(e){return this.rotateOnAxis(aa,e)}rotateZ(e){return this.rotateOnAxis(la,e)}translateOnAxis(e,t){return sa.copy(e).applyQuaternion(this.quaternion),this.position.add(sa.multiplyScalar(t)),this}translateX(e){return this.translateOnAxis(oa,e)}translateY(e){return this.translateOnAxis(aa,e)}translateZ(e){return this.translateOnAxis(la,e)}localToWorld(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(this.matrixWorld)}worldToLocal(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(Mn.copy(this.matrixWorld).invert())}lookAt(e,t,n){e.isVector3?_r.copy(e):_r.set(e,t,n);const r=this.parent;this.updateWorldMatrix(!0,!1),qi.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?Mn.lookAt(qi,_r,this.up):Mn.lookAt(_r,qi,this.up),this.quaternion.setFromRotationMatrix(Mn),r&&(Mn.extractRotation(r.matrixWorld),_i.setFromRotationMatrix(Mn),this.quaternion.premultiply(_i.invert()))}add(e){if(arguments.length>1){for(let t=0;t<arguments.length;t++)this.add(arguments[t]);return this}return e===this?(console.error("THREE.Object3D.add: object can't be added as a child of itself.",e),this):(e&&e.isObject3D?(e.removeFromParent(),e.parent=this,this.children.push(e),e.dispatchEvent(ca),vi.child=e,this.dispatchEvent(vi),vi.child=null):console.error("THREE.Object3D.add: object not an instance of THREE.Object3D.",e),this)}remove(e){if(arguments.length>1){for(let n=0;n<arguments.length;n++)this.remove(arguments[n]);return this}const t=this.children.indexOf(e);return t!==-1&&(e.parent=null,this.children.splice(t,1),e.dispatchEvent(Vc),hs.child=e,this.dispatchEvent(hs),hs.child=null),this}removeFromParent(){const e=this.parent;return e!==null&&e.remove(this),this}clear(){return this.remove(...this.children)}attach(e){return this.updateWorldMatrix(!0,!1),Mn.copy(this.matrixWorld).invert(),e.parent!==null&&(e.parent.updateWorldMatrix(!0,!1),Mn.multiply(e.parent.matrixWorld)),e.applyMatrix4(Mn),e.removeFromParent(),e.parent=this,this.children.push(e),e.updateWorldMatrix(!1,!0),e.dispatchEvent(ca),vi.child=e,this.dispatchEvent(vi),vi.child=null,this}getObjectById(e){return this.getObjectByProperty("id",e)}getObjectByName(e){return this.getObjectByProperty("name",e)}getObjectByProperty(e,t){if(this[e]===t)return this;for(let n=0,r=this.children.length;n<r;n++){const o=this.children[n].getObjectByProperty(e,t);if(o!==void 0)return o}}getObjectsByProperty(e,t,n=[]){this[e]===t&&n.push(this);const r=this.children;for(let s=0,o=r.length;s<o;s++)r[s].getObjectsByProperty(e,t,n);return n}getWorldPosition(e){return this.updateWorldMatrix(!0,!1),e.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(qi,e,Hc),e}getWorldScale(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(qi,kc,e),e}getWorldDirection(e){this.updateWorldMatrix(!0,!1);const t=this.matrixWorld.elements;return e.set(t[8],t[9],t[10]).normalize()}raycast(){}traverse(e){e(this);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverse(e)}traverseVisible(e){if(this.visible===!1)return;e(this);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverseVisible(e)}traverseAncestors(e){const t=this.parent;t!==null&&(e(t),t.traverseAncestors(e))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale),this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(e){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||e)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,e=!0);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].updateMatrixWorld(e)}updateWorldMatrix(e,t){const n=this.parent;if(e===!0&&n!==null&&n.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),t===!0){const r=this.children;for(let s=0,o=r.length;s<o;s++)r[s].updateWorldMatrix(!1,!0)}}toJSON(e){const t=e===void 0||typeof e=="string",n={};t&&(e={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.7,type:"Object",generator:"Object3D.toJSON"});const r={};r.uuid=this.uuid,r.type=this.type,this.name!==""&&(r.name=this.name),this.castShadow===!0&&(r.castShadow=!0),this.receiveShadow===!0&&(r.receiveShadow=!0),this.visible===!1&&(r.visible=!1),this.frustumCulled===!1&&(r.frustumCulled=!1),this.renderOrder!==0&&(r.renderOrder=this.renderOrder),Object.keys(this.userData).length>0&&(r.userData=this.userData),r.layers=this.layers.mask,r.matrix=this.matrix.toArray(),r.up=this.up.toArray(),this.matrixAutoUpdate===!1&&(r.matrixAutoUpdate=!1),this.isInstancedMesh&&(r.type="InstancedMesh",r.count=this.count,r.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(r.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(r.type="BatchedMesh",r.perObjectFrustumCulled=this.perObjectFrustumCulled,r.sortObjects=this.sortObjects,r.drawRanges=this._drawRanges,r.reservedRanges=this._reservedRanges,r.geometryInfo=this._geometryInfo.map(a=>({...a,boundingBox:a.boundingBox?a.boundingBox.toJSON():void 0,boundingSphere:a.boundingSphere?a.boundingSphere.toJSON():void 0})),r.instanceInfo=this._instanceInfo.map(a=>({...a})),r.availableInstanceIds=this._availableInstanceIds.slice(),r.availableGeometryIds=this._availableGeometryIds.slice(),r.nextIndexStart=this._nextIndexStart,r.nextVertexStart=this._nextVertexStart,r.geometryCount=this._geometryCount,r.maxInstanceCount=this._maxInstanceCount,r.maxVertexCount=this._maxVertexCount,r.maxIndexCount=this._maxIndexCount,r.geometryInitialized=this._geometryInitialized,r.matricesTexture=this._matricesTexture.toJSON(e),r.indirectTexture=this._indirectTexture.toJSON(e),this._colorsTexture!==null&&(r.colorsTexture=this._colorsTexture.toJSON(e)),this.boundingSphere!==null&&(r.boundingSphere=this.boundingSphere.toJSON()),this.boundingBox!==null&&(r.boundingBox=this.boundingBox.toJSON()));function s(a,u){return a[u.uuid]===void 0&&(a[u.uuid]=u.toJSON(e)),u.uuid}if(this.isScene)this.background&&(this.background.isColor?r.background=this.background.toJSON():this.background.isTexture&&(r.background=this.background.toJSON(e).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(r.environment=this.environment.toJSON(e).uuid);else if(this.isMesh||this.isLine||this.isPoints){r.geometry=s(e.geometries,this.geometry);const a=this.geometry.parameters;if(a!==void 0&&a.shapes!==void 0){const u=a.shapes;if(Array.isArray(u))for(let l=0,d=u.length;l<d;l++){const h=u[l];s(e.shapes,h)}else s(e.shapes,u)}}if(this.isSkinnedMesh&&(r.bindMode=this.bindMode,r.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(s(e.skeletons,this.skeleton),r.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){const a=[];for(let u=0,l=this.material.length;u<l;u++)a.push(s(e.materials,this.material[u]));r.material=a}else r.material=s(e.materials,this.material);if(this.children.length>0){r.children=[];for(let a=0;a<this.children.length;a++)r.children.push(this.children[a].toJSON(e).object)}if(this.animations.length>0){r.animations=[];for(let a=0;a<this.animations.length;a++){const u=this.animations[a];r.animations.push(s(e.animations,u))}}if(t){const a=o(e.geometries),u=o(e.materials),l=o(e.textures),d=o(e.images),h=o(e.shapes),f=o(e.skeletons),m=o(e.animations),_=o(e.nodes);a.length>0&&(n.geometries=a),u.length>0&&(n.materials=u),l.length>0&&(n.textures=l),d.length>0&&(n.images=d),h.length>0&&(n.shapes=h),f.length>0&&(n.skeletons=f),m.length>0&&(n.animations=m),_.length>0&&(n.nodes=_)}return n.object=r,n;function o(a){const u=[];for(const l in a){const d=a[l];delete d.metadata,u.push(d)}return u}}clone(e){return new this.constructor().copy(this,e)}copy(e,t=!0){if(this.name=e.name,this.up.copy(e.up),this.position.copy(e.position),this.rotation.order=e.rotation.order,this.quaternion.copy(e.quaternion),this.scale.copy(e.scale),this.matrix.copy(e.matrix),this.matrixWorld.copy(e.matrixWorld),this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrixWorldAutoUpdate=e.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=e.matrixWorldNeedsUpdate,this.layers.mask=e.layers.mask,this.visible=e.visible,this.castShadow=e.castShadow,this.receiveShadow=e.receiveShadow,this.frustumCulled=e.frustumCulled,this.renderOrder=e.renderOrder,this.animations=e.animations.slice(),this.userData=JSON.parse(JSON.stringify(e.userData)),t===!0)for(let n=0;n<e.children.length;n++){const r=e.children[n];this.add(r.clone())}return this}}Pt.DEFAULT_UP=new B(0,1,0);Pt.DEFAULT_MATRIX_AUTO_UPDATE=!0;Pt.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;const cn=new B,Sn=new B,ds=new B,yn=new B,xi=new B,Mi=new B,ua=new B,fs=new B,ps=new B,ms=new B,gs=new Mt,_s=new Mt,vs=new Mt;class on{constructor(e=new B,t=new B,n=new B){this.a=e,this.b=t,this.c=n}static getNormal(e,t,n,r){r.subVectors(n,t),cn.subVectors(e,t),r.cross(cn);const s=r.lengthSq();return s>0?r.multiplyScalar(1/Math.sqrt(s)):r.set(0,0,0)}static getBarycoord(e,t,n,r,s){cn.subVectors(r,t),Sn.subVectors(n,t),ds.subVectors(e,t);const o=cn.dot(cn),a=cn.dot(Sn),u=cn.dot(ds),l=Sn.dot(Sn),d=Sn.dot(ds),h=o*l-a*a;if(h===0)return s.set(0,0,0),null;const f=1/h,m=(l*u-a*d)*f,_=(o*d-a*u)*f;return s.set(1-m-_,_,m)}static containsPoint(e,t,n,r){return this.getBarycoord(e,t,n,r,yn)===null?!1:yn.x>=0&&yn.y>=0&&yn.x+yn.y<=1}static getInterpolation(e,t,n,r,s,o,a,u){return this.getBarycoord(e,t,n,r,yn)===null?(u.x=0,u.y=0,"z"in u&&(u.z=0),"w"in u&&(u.w=0),null):(u.setScalar(0),u.addScaledVector(s,yn.x),u.addScaledVector(o,yn.y),u.addScaledVector(a,yn.z),u)}static getInterpolatedAttribute(e,t,n,r,s,o){return gs.setScalar(0),_s.setScalar(0),vs.setScalar(0),gs.fromBufferAttribute(e,t),_s.fromBufferAttribute(e,n),vs.fromBufferAttribute(e,r),o.setScalar(0),o.addScaledVector(gs,s.x),o.addScaledVector(_s,s.y),o.addScaledVector(vs,s.z),o}static isFrontFacing(e,t,n,r){return cn.subVectors(n,t),Sn.subVectors(e,t),cn.cross(Sn).dot(r)<0}set(e,t,n){return this.a.copy(e),this.b.copy(t),this.c.copy(n),this}setFromPointsAndIndices(e,t,n,r){return this.a.copy(e[t]),this.b.copy(e[n]),this.c.copy(e[r]),this}setFromAttributeAndIndices(e,t,n,r){return this.a.fromBufferAttribute(e,t),this.b.fromBufferAttribute(e,n),this.c.fromBufferAttribute(e,r),this}clone(){return new this.constructor().copy(this)}copy(e){return this.a.copy(e.a),this.b.copy(e.b),this.c.copy(e.c),this}getArea(){return cn.subVectors(this.c,this.b),Sn.subVectors(this.a,this.b),cn.cross(Sn).length()*.5}getMidpoint(e){return e.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(e){return on.getNormal(this.a,this.b,this.c,e)}getPlane(e){return e.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(e,t){return on.getBarycoord(e,this.a,this.b,this.c,t)}getInterpolation(e,t,n,r,s){return on.getInterpolation(e,this.a,this.b,this.c,t,n,r,s)}containsPoint(e){return on.containsPoint(e,this.a,this.b,this.c)}isFrontFacing(e){return on.isFrontFacing(this.a,this.b,this.c,e)}intersectsBox(e){return e.intersectsTriangle(this)}closestPointToPoint(e,t){const n=this.a,r=this.b,s=this.c;let o,a;xi.subVectors(r,n),Mi.subVectors(s,n),fs.subVectors(e,n);const u=xi.dot(fs),l=Mi.dot(fs);if(u<=0&&l<=0)return t.copy(n);ps.subVectors(e,r);const d=xi.dot(ps),h=Mi.dot(ps);if(d>=0&&h<=d)return t.copy(r);const f=u*h-d*l;if(f<=0&&u>=0&&d<=0)return o=u/(u-d),t.copy(n).addScaledVector(xi,o);ms.subVectors(e,s);const m=xi.dot(ms),_=Mi.dot(ms);if(_>=0&&m<=_)return t.copy(s);const v=m*l-u*_;if(v<=0&&l>=0&&_<=0)return a=l/(l-_),t.copy(n).addScaledVector(Mi,a);const p=d*_-m*h;if(p<=0&&h-d>=0&&m-_>=0)return ua.subVectors(s,r),a=(h-d)/(h-d+(m-_)),t.copy(r).addScaledVector(ua,a);const c=1/(p+v+f);return o=v*c,a=f*c,t.copy(n).addScaledVector(xi,o).addScaledVector(Mi,a)}equals(e){return e.a.equals(this.a)&&e.b.equals(this.b)&&e.c.equals(this.c)}}const ml={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},Nn={h:0,s:0,l:0},vr={h:0,s:0,l:0};function xs(i,e,t){return t<0&&(t+=1),t>1&&(t-=1),t<1/6?i+(e-i)*6*t:t<1/2?e:t<2/3?i+(e-i)*6*(2/3-t):i}class je{constructor(e,t,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(e,t,n)}set(e,t,n){if(t===void 0&&n===void 0){const r=e;r&&r.isColor?this.copy(r):typeof r=="number"?this.setHex(r):typeof r=="string"&&this.setStyle(r)}else this.setRGB(e,t,n);return this}setScalar(e){return this.r=e,this.g=e,this.b=e,this}setHex(e,t=Dt){return e=Math.floor(e),this.r=(e>>16&255)/255,this.g=(e>>8&255)/255,this.b=(e&255)/255,at.colorSpaceToWorking(this,t),this}setRGB(e,t,n,r=at.workingColorSpace){return this.r=e,this.g=t,this.b=n,at.colorSpaceToWorking(this,r),this}setHSL(e,t,n,r=at.workingColorSpace){if(e=Ac(e,1),t=rt(t,0,1),n=rt(n,0,1),t===0)this.r=this.g=this.b=n;else{const s=n<=.5?n*(1+t):n+t-n*t,o=2*n-s;this.r=xs(o,s,e+1/3),this.g=xs(o,s,e),this.b=xs(o,s,e-1/3)}return at.colorSpaceToWorking(this,r),this}setStyle(e,t=Dt){function n(s){s!==void 0&&parseFloat(s)<1&&console.warn("THREE.Color: Alpha component of "+e+" will be ignored.")}let r;if(r=/^(\w+)\(([^\)]*)\)/.exec(e)){let s;const o=r[1],a=r[2];switch(o){case"rgb":case"rgba":if(s=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(s[4]),this.setRGB(Math.min(255,parseInt(s[1],10))/255,Math.min(255,parseInt(s[2],10))/255,Math.min(255,parseInt(s[3],10))/255,t);if(s=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(s[4]),this.setRGB(Math.min(100,parseInt(s[1],10))/100,Math.min(100,parseInt(s[2],10))/100,Math.min(100,parseInt(s[3],10))/100,t);break;case"hsl":case"hsla":if(s=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(s[4]),this.setHSL(parseFloat(s[1])/360,parseFloat(s[2])/100,parseFloat(s[3])/100,t);break;default:console.warn("THREE.Color: Unknown color model "+e)}}else if(r=/^\#([A-Fa-f\d]+)$/.exec(e)){const s=r[1],o=s.length;if(o===3)return this.setRGB(parseInt(s.charAt(0),16)/15,parseInt(s.charAt(1),16)/15,parseInt(s.charAt(2),16)/15,t);if(o===6)return this.setHex(parseInt(s,16),t);console.warn("THREE.Color: Invalid hex color "+e)}else if(e&&e.length>0)return this.setColorName(e,t);return this}setColorName(e,t=Dt){const n=ml[e.toLowerCase()];return n!==void 0?this.setHex(n,t):console.warn("THREE.Color: Unknown color "+e),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(e){return this.r=e.r,this.g=e.g,this.b=e.b,this}copySRGBToLinear(e){return this.r=Pn(e.r),this.g=Pn(e.g),this.b=Pn(e.b),this}copyLinearToSRGB(e){return this.r=Li(e.r),this.g=Li(e.g),this.b=Li(e.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(e=Dt){return at.workingToColorSpace(Ut.copy(this),e),Math.round(rt(Ut.r*255,0,255))*65536+Math.round(rt(Ut.g*255,0,255))*256+Math.round(rt(Ut.b*255,0,255))}getHexString(e=Dt){return("000000"+this.getHex(e).toString(16)).slice(-6)}getHSL(e,t=at.workingColorSpace){at.workingToColorSpace(Ut.copy(this),t);const n=Ut.r,r=Ut.g,s=Ut.b,o=Math.max(n,r,s),a=Math.min(n,r,s);let u,l;const d=(a+o)/2;if(a===o)u=0,l=0;else{const h=o-a;switch(l=d<=.5?h/(o+a):h/(2-o-a),o){case n:u=(r-s)/h+(r<s?6:0);break;case r:u=(s-n)/h+2;break;case s:u=(n-r)/h+4;break}u/=6}return e.h=u,e.s=l,e.l=d,e}getRGB(e,t=at.workingColorSpace){return at.workingToColorSpace(Ut.copy(this),t),e.r=Ut.r,e.g=Ut.g,e.b=Ut.b,e}getStyle(e=Dt){at.workingToColorSpace(Ut.copy(this),e);const t=Ut.r,n=Ut.g,r=Ut.b;return e!==Dt?`color(${e} ${t.toFixed(3)} ${n.toFixed(3)} ${r.toFixed(3)})`:`rgb(${Math.round(t*255)},${Math.round(n*255)},${Math.round(r*255)})`}offsetHSL(e,t,n){return this.getHSL(Nn),this.setHSL(Nn.h+e,Nn.s+t,Nn.l+n)}add(e){return this.r+=e.r,this.g+=e.g,this.b+=e.b,this}addColors(e,t){return this.r=e.r+t.r,this.g=e.g+t.g,this.b=e.b+t.b,this}addScalar(e){return this.r+=e,this.g+=e,this.b+=e,this}sub(e){return this.r=Math.max(0,this.r-e.r),this.g=Math.max(0,this.g-e.g),this.b=Math.max(0,this.b-e.b),this}multiply(e){return this.r*=e.r,this.g*=e.g,this.b*=e.b,this}multiplyScalar(e){return this.r*=e,this.g*=e,this.b*=e,this}lerp(e,t){return this.r+=(e.r-this.r)*t,this.g+=(e.g-this.g)*t,this.b+=(e.b-this.b)*t,this}lerpColors(e,t,n){return this.r=e.r+(t.r-e.r)*n,this.g=e.g+(t.g-e.g)*n,this.b=e.b+(t.b-e.b)*n,this}lerpHSL(e,t){this.getHSL(Nn),e.getHSL(vr);const n=ts(Nn.h,vr.h,t),r=ts(Nn.s,vr.s,t),s=ts(Nn.l,vr.l,t);return this.setHSL(n,r,s),this}setFromVector3(e){return this.r=e.x,this.g=e.y,this.b=e.z,this}applyMatrix3(e){const t=this.r,n=this.g,r=this.b,s=e.elements;return this.r=s[0]*t+s[3]*n+s[6]*r,this.g=s[1]*t+s[4]*n+s[7]*r,this.b=s[2]*t+s[5]*n+s[8]*r,this}equals(e){return e.r===this.r&&e.g===this.g&&e.b===this.b}fromArray(e,t=0){return this.r=e[t],this.g=e[t+1],this.b=e[t+2],this}toArray(e=[],t=0){return e[t]=this.r,e[t+1]=this.g,e[t+2]=this.b,e}fromBufferAttribute(e,t){return this.r=e.getX(t),this.g=e.getY(t),this.b=e.getZ(t),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}}const Ut=new je;je.NAMES=ml;let Gc=0;class oi extends si{constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:Gc++}),this.uuid=ar(),this.name="",this.type="Material",this.blending=Pi,this.side=Vn,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=Bs,this.blendDst=zs,this.blendEquation=Qn,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new je(0,0,0),this.blendAlpha=0,this.depthFunc=Ui,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=Zo,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=hi,this.stencilZFail=hi,this.stencilZPass=hi,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.allowOverride=!0,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(e){this._alphaTest>0!=e>0&&this.version++,this._alphaTest=e}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(e){if(e!==void 0)for(const t in e){const n=e[t];if(n===void 0){console.warn(`THREE.Material: parameter '${t}' has value of undefined.`);continue}const r=this[t];if(r===void 0){console.warn(`THREE.Material: '${t}' is not a property of THREE.${this.type}.`);continue}r&&r.isColor?r.set(n):r&&r.isVector3&&n&&n.isVector3?r.copy(n):this[t]=n}}toJSON(e){const t=e===void 0||typeof e=="string";t&&(e={textures:{},images:{}});const n={metadata:{version:4.7,type:"Material",generator:"Material.toJSON"}};n.uuid=this.uuid,n.type=this.type,this.name!==""&&(n.name=this.name),this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&this.emissiveIntensity!==1&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(e).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(e).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(e).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(e).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(e).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(e).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(e).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(e).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(e).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(e).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(e).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(e).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(e).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(e).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(e).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(e).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(e).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(e).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(e).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(e).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(e).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(e).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(e).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(e).uuid),this.attenuationDistance!==void 0&&this.attenuationDistance!==1/0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.shadowSide!==null&&(n.shadowSide=this.shadowSide),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),this.blending!==Pi&&(n.blending=this.blending),this.side!==Vn&&(n.side=this.side),this.vertexColors===!0&&(n.vertexColors=!0),this.opacity<1&&(n.opacity=this.opacity),this.transparent===!0&&(n.transparent=!0),this.blendSrc!==Bs&&(n.blendSrc=this.blendSrc),this.blendDst!==zs&&(n.blendDst=this.blendDst),this.blendEquation!==Qn&&(n.blendEquation=this.blendEquation),this.blendSrcAlpha!==null&&(n.blendSrcAlpha=this.blendSrcAlpha),this.blendDstAlpha!==null&&(n.blendDstAlpha=this.blendDstAlpha),this.blendEquationAlpha!==null&&(n.blendEquationAlpha=this.blendEquationAlpha),this.blendColor&&this.blendColor.isColor&&(n.blendColor=this.blendColor.getHex()),this.blendAlpha!==0&&(n.blendAlpha=this.blendAlpha),this.depthFunc!==Ui&&(n.depthFunc=this.depthFunc),this.depthTest===!1&&(n.depthTest=this.depthTest),this.depthWrite===!1&&(n.depthWrite=this.depthWrite),this.colorWrite===!1&&(n.colorWrite=this.colorWrite),this.stencilWriteMask!==255&&(n.stencilWriteMask=this.stencilWriteMask),this.stencilFunc!==Zo&&(n.stencilFunc=this.stencilFunc),this.stencilRef!==0&&(n.stencilRef=this.stencilRef),this.stencilFuncMask!==255&&(n.stencilFuncMask=this.stencilFuncMask),this.stencilFail!==hi&&(n.stencilFail=this.stencilFail),this.stencilZFail!==hi&&(n.stencilZFail=this.stencilZFail),this.stencilZPass!==hi&&(n.stencilZPass=this.stencilZPass),this.stencilWrite===!0&&(n.stencilWrite=this.stencilWrite),this.rotation!==void 0&&this.rotation!==0&&(n.rotation=this.rotation),this.polygonOffset===!0&&(n.polygonOffset=!0),this.polygonOffsetFactor!==0&&(n.polygonOffsetFactor=this.polygonOffsetFactor),this.polygonOffsetUnits!==0&&(n.polygonOffsetUnits=this.polygonOffsetUnits),this.linewidth!==void 0&&this.linewidth!==1&&(n.linewidth=this.linewidth),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.dithering===!0&&(n.dithering=!0),this.alphaTest>0&&(n.alphaTest=this.alphaTest),this.alphaHash===!0&&(n.alphaHash=!0),this.alphaToCoverage===!0&&(n.alphaToCoverage=!0),this.premultipliedAlpha===!0&&(n.premultipliedAlpha=!0),this.forceSinglePass===!0&&(n.forceSinglePass=!0),this.wireframe===!0&&(n.wireframe=!0),this.wireframeLinewidth>1&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!=="round"&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!=="round"&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading===!0&&(n.flatShading=!0),this.visible===!1&&(n.visible=!1),this.toneMapped===!1&&(n.toneMapped=!1),this.fog===!1&&(n.fog=!1),Object.keys(this.userData).length>0&&(n.userData=this.userData);function r(s){const o=[];for(const a in s){const u=s[a];delete u.metadata,o.push(u)}return o}if(t){const s=r(e.textures),o=r(e.images);s.length>0&&(n.textures=s),o.length>0&&(n.images=o)}return n}clone(){return new this.constructor().copy(this)}copy(e){this.name=e.name,this.blending=e.blending,this.side=e.side,this.vertexColors=e.vertexColors,this.opacity=e.opacity,this.transparent=e.transparent,this.blendSrc=e.blendSrc,this.blendDst=e.blendDst,this.blendEquation=e.blendEquation,this.blendSrcAlpha=e.blendSrcAlpha,this.blendDstAlpha=e.blendDstAlpha,this.blendEquationAlpha=e.blendEquationAlpha,this.blendColor.copy(e.blendColor),this.blendAlpha=e.blendAlpha,this.depthFunc=e.depthFunc,this.depthTest=e.depthTest,this.depthWrite=e.depthWrite,this.stencilWriteMask=e.stencilWriteMask,this.stencilFunc=e.stencilFunc,this.stencilRef=e.stencilRef,this.stencilFuncMask=e.stencilFuncMask,this.stencilFail=e.stencilFail,this.stencilZFail=e.stencilZFail,this.stencilZPass=e.stencilZPass,this.stencilWrite=e.stencilWrite;const t=e.clippingPlanes;let n=null;if(t!==null){const r=t.length;n=new Array(r);for(let s=0;s!==r;++s)n[s]=t[s].clone()}return this.clippingPlanes=n,this.clipIntersection=e.clipIntersection,this.clipShadows=e.clipShadows,this.shadowSide=e.shadowSide,this.colorWrite=e.colorWrite,this.precision=e.precision,this.polygonOffset=e.polygonOffset,this.polygonOffsetFactor=e.polygonOffsetFactor,this.polygonOffsetUnits=e.polygonOffsetUnits,this.dithering=e.dithering,this.alphaTest=e.alphaTest,this.alphaHash=e.alphaHash,this.alphaToCoverage=e.alphaToCoverage,this.premultipliedAlpha=e.premultipliedAlpha,this.forceSinglePass=e.forceSinglePass,this.visible=e.visible,this.toneMapped=e.toneMapped,this.userData=JSON.parse(JSON.stringify(e.userData)),this}dispose(){this.dispatchEvent({type:"dispose"})}set needsUpdate(e){e===!0&&this.version++}}class Bo extends oi{constructor(e){super(),this.isMeshBasicMaterial=!0,this.type="MeshBasicMaterial",this.color=new je(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new fn,this.combine=Ro,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.fog=e.fog,this}}const St=new B,xr=new Ye;let Wc=0;class Bt{constructor(e,t,n=!1){if(Array.isArray(e))throw new TypeError("THREE.BufferAttribute: array should be a Typed Array.");this.isBufferAttribute=!0,Object.defineProperty(this,"id",{value:Wc++}),this.name="",this.array=e,this.itemSize=t,this.count=e!==void 0?e.length/t:0,this.normalized=n,this.usage=$o,this.updateRanges=[],this.gpuType=Cn,this.version=0}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.name=e.name,this.array=new e.array.constructor(e.array),this.itemSize=e.itemSize,this.count=e.count,this.normalized=e.normalized,this.usage=e.usage,this.gpuType=e.gpuType,this}copyAt(e,t,n){e*=this.itemSize,n*=t.itemSize;for(let r=0,s=this.itemSize;r<s;r++)this.array[e+r]=t.array[n+r];return this}copyArray(e){return this.array.set(e),this}applyMatrix3(e){if(this.itemSize===2)for(let t=0,n=this.count;t<n;t++)xr.fromBufferAttribute(this,t),xr.applyMatrix3(e),this.setXY(t,xr.x,xr.y);else if(this.itemSize===3)for(let t=0,n=this.count;t<n;t++)St.fromBufferAttribute(this,t),St.applyMatrix3(e),this.setXYZ(t,St.x,St.y,St.z);return this}applyMatrix4(e){for(let t=0,n=this.count;t<n;t++)St.fromBufferAttribute(this,t),St.applyMatrix4(e),this.setXYZ(t,St.x,St.y,St.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)St.fromBufferAttribute(this,t),St.applyNormalMatrix(e),this.setXYZ(t,St.x,St.y,St.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)St.fromBufferAttribute(this,t),St.transformDirection(e),this.setXYZ(t,St.x,St.y,St.z);return this}set(e,t=0){return this.array.set(e,t),this}getComponent(e,t){let n=this.array[e*this.itemSize+t];return this.normalized&&(n=Gi(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=Ht(n,this.array)),this.array[e*this.itemSize+t]=n,this}getX(e){let t=this.array[e*this.itemSize];return this.normalized&&(t=Gi(t,this.array)),t}setX(e,t){return this.normalized&&(t=Ht(t,this.array)),this.array[e*this.itemSize]=t,this}getY(e){let t=this.array[e*this.itemSize+1];return this.normalized&&(t=Gi(t,this.array)),t}setY(e,t){return this.normalized&&(t=Ht(t,this.array)),this.array[e*this.itemSize+1]=t,this}getZ(e){let t=this.array[e*this.itemSize+2];return this.normalized&&(t=Gi(t,this.array)),t}setZ(e,t){return this.normalized&&(t=Ht(t,this.array)),this.array[e*this.itemSize+2]=t,this}getW(e){let t=this.array[e*this.itemSize+3];return this.normalized&&(t=Gi(t,this.array)),t}setW(e,t){return this.normalized&&(t=Ht(t,this.array)),this.array[e*this.itemSize+3]=t,this}setXY(e,t,n){return e*=this.itemSize,this.normalized&&(t=Ht(t,this.array),n=Ht(n,this.array)),this.array[e+0]=t,this.array[e+1]=n,this}setXYZ(e,t,n,r){return e*=this.itemSize,this.normalized&&(t=Ht(t,this.array),n=Ht(n,this.array),r=Ht(r,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this}setXYZW(e,t,n,r,s){return e*=this.itemSize,this.normalized&&(t=Ht(t,this.array),n=Ht(n,this.array),r=Ht(r,this.array),s=Ht(s,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this.array[e+3]=s,this}onUpload(e){return this.onUploadCallback=e,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){const e={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return this.name!==""&&(e.name=this.name),this.usage!==$o&&(e.usage=this.usage),e}}class gl extends Bt{constructor(e,t,n){super(new Uint16Array(e),t,n)}}class _l extends Bt{constructor(e,t,n){super(new Uint32Array(e),t,n)}}class lt extends Bt{constructor(e,t,n){super(new Float32Array(e),t,n)}}let Xc=0;const nn=new gt,Ms=new Pt,Si=new B,jt=new Bi,Yi=new Bi,Ct=new B;class yt extends si{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:Xc++}),this.uuid=ar(),this.name="",this.type="BufferGeometry",this.index=null,this.indirect=null,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={}}getIndex(){return this.index}setIndex(e){return Array.isArray(e)?this.index=new(fl(e)?_l:gl)(e,1):this.index=e,this}setIndirect(e){return this.indirect=e,this}getIndirect(){return this.indirect}getAttribute(e){return this.attributes[e]}setAttribute(e,t){return this.attributes[e]=t,this}deleteAttribute(e){return delete this.attributes[e],this}hasAttribute(e){return this.attributes[e]!==void 0}addGroup(e,t,n=0){this.groups.push({start:e,count:t,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(e,t){this.drawRange.start=e,this.drawRange.count=t}applyMatrix4(e){const t=this.attributes.position;t!==void 0&&(t.applyMatrix4(e),t.needsUpdate=!0);const n=this.attributes.normal;if(n!==void 0){const s=new Qe().getNormalMatrix(e);n.applyNormalMatrix(s),n.needsUpdate=!0}const r=this.attributes.tangent;return r!==void 0&&(r.transformDirection(e),r.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}applyQuaternion(e){return nn.makeRotationFromQuaternion(e),this.applyMatrix4(nn),this}rotateX(e){return nn.makeRotationX(e),this.applyMatrix4(nn),this}rotateY(e){return nn.makeRotationY(e),this.applyMatrix4(nn),this}rotateZ(e){return nn.makeRotationZ(e),this.applyMatrix4(nn),this}translate(e,t,n){return nn.makeTranslation(e,t,n),this.applyMatrix4(nn),this}scale(e,t,n){return nn.makeScale(e,t,n),this.applyMatrix4(nn),this}lookAt(e){return Ms.lookAt(e),Ms.updateMatrix(),this.applyMatrix4(Ms.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(Si).negate(),this.translate(Si.x,Si.y,Si.z),this}setFromPoints(e){const t=this.getAttribute("position");if(t===void 0){const n=[];for(let r=0,s=e.length;r<s;r++){const o=e[r];n.push(o.x,o.y,o.z||0)}this.setAttribute("position",new lt(n,3))}else{const n=Math.min(e.length,t.count);for(let r=0;r<n;r++){const s=e[r];t.setXYZ(r,s.x,s.y,s.z||0)}e.length>t.count&&console.warn("THREE.BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry."),t.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new Bi);const e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.",this),this.boundingBox.set(new B(-1/0,-1/0,-1/0),new B(1/0,1/0,1/0));return}if(e!==void 0){if(this.boundingBox.setFromBufferAttribute(e),t)for(let n=0,r=t.length;n<r;n++){const s=t[n];jt.setFromBufferAttribute(s),this.morphTargetsRelative?(Ct.addVectors(this.boundingBox.min,jt.min),this.boundingBox.expandByPoint(Ct),Ct.addVectors(this.boundingBox.max,jt.max),this.boundingBox.expandByPoint(Ct)):(this.boundingBox.expandByPoint(jt.min),this.boundingBox.expandByPoint(jt.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&console.error('THREE.BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.',this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new Kr);const e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.",this),this.boundingSphere.set(new B,1/0);return}if(e){const n=this.boundingSphere.center;if(jt.setFromBufferAttribute(e),t)for(let s=0,o=t.length;s<o;s++){const a=t[s];Yi.setFromBufferAttribute(a),this.morphTargetsRelative?(Ct.addVectors(jt.min,Yi.min),jt.expandByPoint(Ct),Ct.addVectors(jt.max,Yi.max),jt.expandByPoint(Ct)):(jt.expandByPoint(Yi.min),jt.expandByPoint(Yi.max))}jt.getCenter(n);let r=0;for(let s=0,o=e.count;s<o;s++)Ct.fromBufferAttribute(e,s),r=Math.max(r,n.distanceToSquared(Ct));if(t)for(let s=0,o=t.length;s<o;s++){const a=t[s],u=this.morphTargetsRelative;for(let l=0,d=a.count;l<d;l++)Ct.fromBufferAttribute(a,l),u&&(Si.fromBufferAttribute(e,l),Ct.add(Si)),r=Math.max(r,n.distanceToSquared(Ct))}this.boundingSphere.radius=Math.sqrt(r),isNaN(this.boundingSphere.radius)&&console.error('THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.',this)}}computeTangents(){const e=this.index,t=this.attributes;if(e===null||t.position===void 0||t.normal===void 0||t.uv===void 0){console.error("THREE.BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)");return}const n=t.position,r=t.normal,s=t.uv;this.hasAttribute("tangent")===!1&&this.setAttribute("tangent",new Bt(new Float32Array(4*n.count),4));const o=this.getAttribute("tangent"),a=[],u=[];for(let I=0;I<n.count;I++)a[I]=new B,u[I]=new B;const l=new B,d=new B,h=new B,f=new Ye,m=new Ye,_=new Ye,v=new B,p=new B;function c(I,y,E){l.fromBufferAttribute(n,I),d.fromBufferAttribute(n,y),h.fromBufferAttribute(n,E),f.fromBufferAttribute(s,I),m.fromBufferAttribute(s,y),_.fromBufferAttribute(s,E),d.sub(l),h.sub(l),m.sub(f),_.sub(f);const w=1/(m.x*_.y-_.x*m.y);isFinite(w)&&(v.copy(d).multiplyScalar(_.y).addScaledVector(h,-m.y).multiplyScalar(w),p.copy(h).multiplyScalar(m.x).addScaledVector(d,-_.x).multiplyScalar(w),a[I].add(v),a[y].add(v),a[E].add(v),u[I].add(p),u[y].add(p),u[E].add(p))}let A=this.groups;A.length===0&&(A=[{start:0,count:e.count}]);for(let I=0,y=A.length;I<y;++I){const E=A[I],w=E.start,Q=E.count;for(let j=w,Z=w+Q;j<Z;j+=3)c(e.getX(j+0),e.getX(j+1),e.getX(j+2))}const S=new B,M=new B,C=new B,R=new B;function P(I){C.fromBufferAttribute(r,I),R.copy(C);const y=a[I];S.copy(y),S.sub(C.multiplyScalar(C.dot(y))).normalize(),M.crossVectors(R,y);const w=M.dot(u[I])<0?-1:1;o.setXYZW(I,S.x,S.y,S.z,w)}for(let I=0,y=A.length;I<y;++I){const E=A[I],w=E.start,Q=E.count;for(let j=w,Z=w+Q;j<Z;j+=3)P(e.getX(j+0)),P(e.getX(j+1)),P(e.getX(j+2))}}computeVertexNormals(){const e=this.index,t=this.getAttribute("position");if(t!==void 0){let n=this.getAttribute("normal");if(n===void 0)n=new Bt(new Float32Array(t.count*3),3),this.setAttribute("normal",n);else for(let f=0,m=n.count;f<m;f++)n.setXYZ(f,0,0,0);const r=new B,s=new B,o=new B,a=new B,u=new B,l=new B,d=new B,h=new B;if(e)for(let f=0,m=e.count;f<m;f+=3){const _=e.getX(f+0),v=e.getX(f+1),p=e.getX(f+2);r.fromBufferAttribute(t,_),s.fromBufferAttribute(t,v),o.fromBufferAttribute(t,p),d.subVectors(o,s),h.subVectors(r,s),d.cross(h),a.fromBufferAttribute(n,_),u.fromBufferAttribute(n,v),l.fromBufferAttribute(n,p),a.add(d),u.add(d),l.add(d),n.setXYZ(_,a.x,a.y,a.z),n.setXYZ(v,u.x,u.y,u.z),n.setXYZ(p,l.x,l.y,l.z)}else for(let f=0,m=t.count;f<m;f+=3)r.fromBufferAttribute(t,f+0),s.fromBufferAttribute(t,f+1),o.fromBufferAttribute(t,f+2),d.subVectors(o,s),h.subVectors(r,s),d.cross(h),n.setXYZ(f+0,d.x,d.y,d.z),n.setXYZ(f+1,d.x,d.y,d.z),n.setXYZ(f+2,d.x,d.y,d.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){const e=this.attributes.normal;for(let t=0,n=e.count;t<n;t++)Ct.fromBufferAttribute(e,t),Ct.normalize(),e.setXYZ(t,Ct.x,Ct.y,Ct.z)}toNonIndexed(){function e(a,u){const l=a.array,d=a.itemSize,h=a.normalized,f=new l.constructor(u.length*d);let m=0,_=0;for(let v=0,p=u.length;v<p;v++){a.isInterleavedBufferAttribute?m=u[v]*a.data.stride+a.offset:m=u[v]*d;for(let c=0;c<d;c++)f[_++]=l[m++]}return new Bt(f,d,h)}if(this.index===null)return console.warn("THREE.BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed."),this;const t=new yt,n=this.index.array,r=this.attributes;for(const a in r){const u=r[a],l=e(u,n);t.setAttribute(a,l)}const s=this.morphAttributes;for(const a in s){const u=[],l=s[a];for(let d=0,h=l.length;d<h;d++){const f=l[d],m=e(f,n);u.push(m)}t.morphAttributes[a]=u}t.morphTargetsRelative=this.morphTargetsRelative;const o=this.groups;for(let a=0,u=o.length;a<u;a++){const l=o[a];t.addGroup(l.start,l.count,l.materialIndex)}return t}toJSON(){const e={metadata:{version:4.7,type:"BufferGeometry",generator:"BufferGeometry.toJSON"}};if(e.uuid=this.uuid,e.type=this.type,this.name!==""&&(e.name=this.name),Object.keys(this.userData).length>0&&(e.userData=this.userData),this.parameters!==void 0){const u=this.parameters;for(const l in u)u[l]!==void 0&&(e[l]=u[l]);return e}e.data={attributes:{}};const t=this.index;t!==null&&(e.data.index={type:t.array.constructor.name,array:Array.prototype.slice.call(t.array)});const n=this.attributes;for(const u in n){const l=n[u];e.data.attributes[u]=l.toJSON(e.data)}const r={};let s=!1;for(const u in this.morphAttributes){const l=this.morphAttributes[u],d=[];for(let h=0,f=l.length;h<f;h++){const m=l[h];d.push(m.toJSON(e.data))}d.length>0&&(r[u]=d,s=!0)}s&&(e.data.morphAttributes=r,e.data.morphTargetsRelative=this.morphTargetsRelative);const o=this.groups;o.length>0&&(e.data.groups=JSON.parse(JSON.stringify(o)));const a=this.boundingSphere;return a!==null&&(e.data.boundingSphere=a.toJSON()),e}clone(){return new this.constructor().copy(this)}copy(e){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;const t={};this.name=e.name;const n=e.index;n!==null&&this.setIndex(n.clone());const r=e.attributes;for(const l in r){const d=r[l];this.setAttribute(l,d.clone(t))}const s=e.morphAttributes;for(const l in s){const d=[],h=s[l];for(let f=0,m=h.length;f<m;f++)d.push(h[f].clone(t));this.morphAttributes[l]=d}this.morphTargetsRelative=e.morphTargetsRelative;const o=e.groups;for(let l=0,d=o.length;l<d;l++){const h=o[l];this.addGroup(h.start,h.count,h.materialIndex)}const a=e.boundingBox;a!==null&&(this.boundingBox=a.clone());const u=e.boundingSphere;return u!==null&&(this.boundingSphere=u.clone()),this.drawRange.start=e.drawRange.start,this.drawRange.count=e.drawRange.count,this.userData=e.userData,this}dispose(){this.dispatchEvent({type:"dispose"})}}const ha=new gt,jn=new Zr,Mr=new Kr,da=new B,Sr=new B,yr=new B,Er=new B,Ss=new B,Tr=new B,fa=new B,br=new B;class Ft extends Pt{constructor(e=new yt,t=new Bo){super(),this.isMesh=!0,this.type="Mesh",this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.count=1,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),e.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=e.morphTargetInfluences.slice()),e.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},e.morphTargetDictionary)),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}updateMorphTargets(){const t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){const r=t[n[0]];if(r!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let s=0,o=r.length;s<o;s++){const a=r[s].name||String(s);this.morphTargetInfluences.push(0),this.morphTargetDictionary[a]=s}}}}getVertexPosition(e,t){const n=this.geometry,r=n.attributes.position,s=n.morphAttributes.position,o=n.morphTargetsRelative;t.fromBufferAttribute(r,e);const a=this.morphTargetInfluences;if(s&&a){Tr.set(0,0,0);for(let u=0,l=s.length;u<l;u++){const d=a[u],h=s[u];d!==0&&(Ss.fromBufferAttribute(h,e),o?Tr.addScaledVector(Ss,d):Tr.addScaledVector(Ss.sub(t),d))}t.add(Tr)}return t}raycast(e,t){const n=this.geometry,r=this.material,s=this.matrixWorld;r!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),Mr.copy(n.boundingSphere),Mr.applyMatrix4(s),jn.copy(e.ray).recast(e.near),!(Mr.containsPoint(jn.origin)===!1&&(jn.intersectSphere(Mr,da)===null||jn.origin.distanceToSquared(da)>(e.far-e.near)**2))&&(ha.copy(s).invert(),jn.copy(e.ray).applyMatrix4(ha),!(n.boundingBox!==null&&jn.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(e,t,jn)))}_computeIntersections(e,t,n){let r;const s=this.geometry,o=this.material,a=s.index,u=s.attributes.position,l=s.attributes.uv,d=s.attributes.uv1,h=s.attributes.normal,f=s.groups,m=s.drawRange;if(a!==null)if(Array.isArray(o))for(let _=0,v=f.length;_<v;_++){const p=f[_],c=o[p.materialIndex],A=Math.max(p.start,m.start),S=Math.min(a.count,Math.min(p.start+p.count,m.start+m.count));for(let M=A,C=S;M<C;M+=3){const R=a.getX(M),P=a.getX(M+1),I=a.getX(M+2);r=Ar(this,c,e,n,l,d,h,R,P,I),r&&(r.faceIndex=Math.floor(M/3),r.face.materialIndex=p.materialIndex,t.push(r))}}else{const _=Math.max(0,m.start),v=Math.min(a.count,m.start+m.count);for(let p=_,c=v;p<c;p+=3){const A=a.getX(p),S=a.getX(p+1),M=a.getX(p+2);r=Ar(this,o,e,n,l,d,h,A,S,M),r&&(r.faceIndex=Math.floor(p/3),t.push(r))}}else if(u!==void 0)if(Array.isArray(o))for(let _=0,v=f.length;_<v;_++){const p=f[_],c=o[p.materialIndex],A=Math.max(p.start,m.start),S=Math.min(u.count,Math.min(p.start+p.count,m.start+m.count));for(let M=A,C=S;M<C;M+=3){const R=M,P=M+1,I=M+2;r=Ar(this,c,e,n,l,d,h,R,P,I),r&&(r.faceIndex=Math.floor(M/3),r.face.materialIndex=p.materialIndex,t.push(r))}}else{const _=Math.max(0,m.start),v=Math.min(u.count,m.start+m.count);for(let p=_,c=v;p<c;p+=3){const A=p,S=p+1,M=p+2;r=Ar(this,o,e,n,l,d,h,A,S,M),r&&(r.faceIndex=Math.floor(p/3),t.push(r))}}}}function qc(i,e,t,n,r,s,o,a){let u;if(e.side===Wt?u=n.intersectTriangle(o,s,r,!0,a):u=n.intersectTriangle(r,s,o,e.side===Vn,a),u===null)return null;br.copy(a),br.applyMatrix4(i.matrixWorld);const l=t.ray.origin.distanceTo(br);return l<t.near||l>t.far?null:{distance:l,point:br.clone(),object:i}}function Ar(i,e,t,n,r,s,o,a,u,l){i.getVertexPosition(a,Sr),i.getVertexPosition(u,yr),i.getVertexPosition(l,Er);const d=qc(i,e,t,n,Sr,yr,Er,fa);if(d){const h=new B;on.getBarycoord(fa,Sr,yr,Er,h),r&&(d.uv=on.getInterpolatedAttribute(r,a,u,l,h,new Ye)),s&&(d.uv1=on.getInterpolatedAttribute(s,a,u,l,h,new Ye)),o&&(d.normal=on.getInterpolatedAttribute(o,a,u,l,h,new B),d.normal.dot(n.direction)>0&&d.normal.multiplyScalar(-1));const f={a,b:u,c:l,normal:new B,materialIndex:0};on.getNormal(Sr,yr,Er,f.normal),d.face=f,d.barycoord=h}return d}class lr extends yt{constructor(e=1,t=1,n=1,r=1,s=1,o=1){super(),this.type="BoxGeometry",this.parameters={width:e,height:t,depth:n,widthSegments:r,heightSegments:s,depthSegments:o};const a=this;r=Math.floor(r),s=Math.floor(s),o=Math.floor(o);const u=[],l=[],d=[],h=[];let f=0,m=0;_("z","y","x",-1,-1,n,t,e,o,s,0),_("z","y","x",1,-1,n,t,-e,o,s,1),_("x","z","y",1,1,e,n,t,r,o,2),_("x","z","y",1,-1,e,n,-t,r,o,3),_("x","y","z",1,-1,e,t,n,r,s,4),_("x","y","z",-1,-1,e,t,-n,r,s,5),this.setIndex(u),this.setAttribute("position",new lt(l,3)),this.setAttribute("normal",new lt(d,3)),this.setAttribute("uv",new lt(h,2));function _(v,p,c,A,S,M,C,R,P,I,y){const E=M/P,w=C/I,Q=M/2,j=C/2,Z=R/2,re=P+1,X=I+1;let ae=0,W=0;const he=new B;for(let ye=0;ye<X;ye++){const Te=ye*w-j;for(let ze=0;ze<re;ze++){const nt=ze*E-Q;he[v]=nt*A,he[p]=Te*S,he[c]=Z,l.push(he.x,he.y,he.z),he[v]=0,he[p]=0,he[c]=R>0?1:-1,d.push(he.x,he.y,he.z),h.push(ze/P),h.push(1-ye/I),ae+=1}}for(let ye=0;ye<I;ye++)for(let Te=0;Te<P;Te++){const ze=f+Te+re*ye,nt=f+Te+re*(ye+1),it=f+(Te+1)+re*(ye+1),J=f+(Te+1)+re*ye;u.push(ze,nt,J),u.push(nt,it,J),W+=6}a.addGroup(m,W,y),m+=W,f+=ae}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new lr(e.width,e.height,e.depth,e.widthSegments,e.heightSegments,e.depthSegments)}}function Oi(i){const e={};for(const t in i){e[t]={};for(const n in i[t]){const r=i[t][n];r&&(r.isColor||r.isMatrix3||r.isMatrix4||r.isVector2||r.isVector3||r.isVector4||r.isTexture||r.isQuaternion)?r.isRenderTargetTexture?(console.warn("UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms()."),e[t][n]=null):e[t][n]=r.clone():Array.isArray(r)?e[t][n]=r.slice():e[t][n]=r}}return e}function Nt(i){const e={};for(let t=0;t<i.length;t++){const n=Oi(i[t]);for(const r in n)e[r]=n[r]}return e}function Yc(i){const e=[];for(let t=0;t<i.length;t++)e.push(i[t].clone());return e}function vl(i){const e=i.getRenderTarget();return e===null?i.outputColorSpace:e.isXRRenderTarget===!0?e.texture.colorSpace:at.workingColorSpace}const jc={clone:Oi,merge:Nt};var Kc=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,Zc=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`;class Gn extends oi{constructor(e){super(),this.isShaderMaterial=!0,this.type="ShaderMaterial",this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=Kc,this.fragmentShader=Zc,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,e!==void 0&&this.setValues(e)}copy(e){return super.copy(e),this.fragmentShader=e.fragmentShader,this.vertexShader=e.vertexShader,this.uniforms=Oi(e.uniforms),this.uniformsGroups=Yc(e.uniformsGroups),this.defines=Object.assign({},e.defines),this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.fog=e.fog,this.lights=e.lights,this.clipping=e.clipping,this.extensions=Object.assign({},e.extensions),this.glslVersion=e.glslVersion,this}toJSON(e){const t=super.toJSON(e);t.glslVersion=this.glslVersion,t.uniforms={};for(const r in this.uniforms){const o=this.uniforms[r].value;o&&o.isTexture?t.uniforms[r]={type:"t",value:o.toJSON(e).uuid}:o&&o.isColor?t.uniforms[r]={type:"c",value:o.getHex()}:o&&o.isVector2?t.uniforms[r]={type:"v2",value:o.toArray()}:o&&o.isVector3?t.uniforms[r]={type:"v3",value:o.toArray()}:o&&o.isVector4?t.uniforms[r]={type:"v4",value:o.toArray()}:o&&o.isMatrix3?t.uniforms[r]={type:"m3",value:o.toArray()}:o&&o.isMatrix4?t.uniforms[r]={type:"m4",value:o.toArray()}:t.uniforms[r]={value:o}}Object.keys(this.defines).length>0&&(t.defines=this.defines),t.vertexShader=this.vertexShader,t.fragmentShader=this.fragmentShader,t.lights=this.lights,t.clipping=this.clipping;const n={};for(const r in this.extensions)this.extensions[r]===!0&&(n[r]=!0);return Object.keys(n).length>0&&(t.extensions=n),t}}class xl extends Pt{constructor(){super(),this.isCamera=!0,this.type="Camera",this.matrixWorldInverse=new gt,this.projectionMatrix=new gt,this.projectionMatrixInverse=new gt,this.coordinateSystem=gn,this._reversedDepth=!1}get reversedDepth(){return this._reversedDepth}copy(e,t){return super.copy(e,t),this.matrixWorldInverse.copy(e.matrixWorldInverse),this.projectionMatrix.copy(e.projectionMatrix),this.projectionMatrixInverse.copy(e.projectionMatrixInverse),this.coordinateSystem=e.coordinateSystem,this}getWorldDirection(e){return super.getWorldDirection(e).negate()}updateMatrixWorld(e){super.updateMatrixWorld(e),this.matrixWorldInverse.copy(this.matrixWorld).invert()}updateWorldMatrix(e,t){super.updateWorldMatrix(e,t),this.matrixWorldInverse.copy(this.matrixWorld).invert()}clone(){return new this.constructor().copy(this)}}const Fn=new B,pa=new Ye,ma=new Ye;class sn extends xl{constructor(e=50,t=1,n=.1,r=2e3){super(),this.isPerspectiveCamera=!0,this.type="PerspectiveCamera",this.fov=e,this.zoom=1,this.near=n,this.far=r,this.focus=10,this.aspect=t,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.fov=e.fov,this.zoom=e.zoom,this.near=e.near,this.far=e.far,this.focus=e.focus,this.aspect=e.aspect,this.view=e.view===null?null:Object.assign({},e.view),this.filmGauge=e.filmGauge,this.filmOffset=e.filmOffset,this}setFocalLength(e){const t=.5*this.getFilmHeight()/e;this.fov=yo*2*Math.atan(t),this.updateProjectionMatrix()}getFocalLength(){const e=Math.tan(Zi*.5*this.fov);return .5*this.getFilmHeight()/e}getEffectiveFOV(){return yo*2*Math.atan(Math.tan(Zi*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(e,t,n){Fn.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),t.set(Fn.x,Fn.y).multiplyScalar(-e/Fn.z),Fn.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(Fn.x,Fn.y).multiplyScalar(-e/Fn.z)}getViewSize(e,t){return this.getViewBounds(e,pa,ma),t.subVectors(ma,pa)}setViewOffset(e,t,n,r,s,o){this.aspect=e/t,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=s,this.view.height=o,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){const e=this.near;let t=e*Math.tan(Zi*.5*this.fov)/this.zoom,n=2*t,r=this.aspect*n,s=-.5*r;const o=this.view;if(this.view!==null&&this.view.enabled){const u=o.fullWidth,l=o.fullHeight;s+=o.offsetX*r/u,t-=o.offsetY*n/l,r*=o.width/u,n*=o.height/l}const a=this.filmOffset;a!==0&&(s+=e*a/this.getFilmWidth()),this.projectionMatrix.makePerspective(s,s+r,t,t-n,e,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){const t=super.toJSON(e);return t.object.fov=this.fov,t.object.zoom=this.zoom,t.object.near=this.near,t.object.far=this.far,t.object.focus=this.focus,t.object.aspect=this.aspect,this.view!==null&&(t.object.view=Object.assign({},this.view)),t.object.filmGauge=this.filmGauge,t.object.filmOffset=this.filmOffset,t}}const yi=-90,Ei=1;class $c extends Pt{constructor(e,t,n){super(),this.type="CubeCamera",this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;const r=new sn(yi,Ei,e,t);r.layers=this.layers,this.add(r);const s=new sn(yi,Ei,e,t);s.layers=this.layers,this.add(s);const o=new sn(yi,Ei,e,t);o.layers=this.layers,this.add(o);const a=new sn(yi,Ei,e,t);a.layers=this.layers,this.add(a);const u=new sn(yi,Ei,e,t);u.layers=this.layers,this.add(u);const l=new sn(yi,Ei,e,t);l.layers=this.layers,this.add(l)}updateCoordinateSystem(){const e=this.coordinateSystem,t=this.children.concat(),[n,r,s,o,a,u]=t;for(const l of t)this.remove(l);if(e===gn)n.up.set(0,1,0),n.lookAt(1,0,0),r.up.set(0,1,0),r.lookAt(-1,0,0),s.up.set(0,0,-1),s.lookAt(0,1,0),o.up.set(0,0,1),o.lookAt(0,-1,0),a.up.set(0,1,0),a.lookAt(0,0,1),u.up.set(0,1,0),u.lookAt(0,0,-1);else if(e===Xr)n.up.set(0,-1,0),n.lookAt(-1,0,0),r.up.set(0,-1,0),r.lookAt(1,0,0),s.up.set(0,0,1),s.lookAt(0,1,0),o.up.set(0,0,-1),o.lookAt(0,-1,0),a.up.set(0,-1,0),a.lookAt(0,0,1),u.up.set(0,-1,0),u.lookAt(0,0,-1);else throw new Error("THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: "+e);for(const l of t)this.add(l),l.updateMatrixWorld()}update(e,t){this.parent===null&&this.updateMatrixWorld();const{renderTarget:n,activeMipmapLevel:r}=this;this.coordinateSystem!==e.coordinateSystem&&(this.coordinateSystem=e.coordinateSystem,this.updateCoordinateSystem());const[s,o,a,u,l,d]=this.children,h=e.getRenderTarget(),f=e.getActiveCubeFace(),m=e.getActiveMipmapLevel(),_=e.xr.enabled;e.xr.enabled=!1;const v=n.texture.generateMipmaps;n.texture.generateMipmaps=!1,e.setRenderTarget(n,0,r),e.render(t,s),e.setRenderTarget(n,1,r),e.render(t,o),e.setRenderTarget(n,2,r),e.render(t,a),e.setRenderTarget(n,3,r),e.render(t,u),e.setRenderTarget(n,4,r),e.render(t,l),n.texture.generateMipmaps=v,e.setRenderTarget(n,5,r),e.render(t,d),e.setRenderTarget(h,f,m),e.xr.enabled=_,n.texture.needsPMREMUpdate=!0}}class Ml extends Ot{constructor(e=[],t=Ii,n,r,s,o,a,u,l,d){super(e,t,n,r,s,o,a,u,l,d),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(e){this.image=e}}class Jc extends ri{constructor(e=1,t={}){super(e,e,t),this.isWebGLCubeRenderTarget=!0;const n={width:e,height:e,depth:1},r=[n,n,n,n,n,n];this.texture=new Ml(r),this._setTextureOptions(t),this.texture.isRenderTargetTexture=!0}fromEquirectangularTexture(e,t){this.texture.type=t.type,this.texture.colorSpace=t.colorSpace,this.texture.generateMipmaps=t.generateMipmaps,this.texture.minFilter=t.minFilter,this.texture.magFilter=t.magFilter;const n={uniforms:{tEquirect:{value:null}},vertexShader:`

				varying vec3 vWorldDirection;

				vec3 transformDirection( in vec3 dir, in mat4 matrix ) {

					return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );

				}

				void main() {

					vWorldDirection = transformDirection( position, modelMatrix );

					#include <begin_vertex>
					#include <project_vertex>

				}
			`,fragmentShader:`

				uniform sampler2D tEquirect;

				varying vec3 vWorldDirection;

				#include <common>

				void main() {

					vec3 direction = normalize( vWorldDirection );

					vec2 sampleUV = equirectUv( direction );

					gl_FragColor = texture2D( tEquirect, sampleUV );

				}
			`},r=new lr(5,5,5),s=new Gn({name:"CubemapFromEquirect",uniforms:Oi(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:Wt,blending:Hn});s.uniforms.tEquirect.value=t;const o=new Ft(r,s),a=t.minFilter;return t.minFilter===Rn&&(t.minFilter=Gt),new $c(1,10,this).update(e,o),t.minFilter=a,o.geometry.dispose(),o.material.dispose(),this}clear(e,t=!0,n=!0,r=!0){const s=e.getRenderTarget();for(let o=0;o<6;o++)e.setRenderTarget(this,o),e.clear(t,n,r);e.setRenderTarget(s)}}class zn extends Pt{constructor(){super(),this.isGroup=!0,this.type="Group"}}const Qc={type:"move"};class ys{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new zn,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new zn,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new B,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new B),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new zn,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new B,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new B),this._grip}dispatchEvent(e){return this._targetRay!==null&&this._targetRay.dispatchEvent(e),this._grip!==null&&this._grip.dispatchEvent(e),this._hand!==null&&this._hand.dispatchEvent(e),this}connect(e){if(e&&e.hand){const t=this._hand;if(t)for(const n of e.hand.values())this._getHandJoint(t,n)}return this.dispatchEvent({type:"connected",data:e}),this}disconnect(e){return this.dispatchEvent({type:"disconnected",data:e}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(e,t,n){let r=null,s=null,o=null;const a=this._targetRay,u=this._grip,l=this._hand;if(e&&t.session.visibilityState!=="visible-blurred"){if(l&&e.hand){o=!0;for(const v of e.hand.values()){const p=t.getJointPose(v,n),c=this._getHandJoint(l,v);p!==null&&(c.matrix.fromArray(p.transform.matrix),c.matrix.decompose(c.position,c.rotation,c.scale),c.matrixWorldNeedsUpdate=!0,c.jointRadius=p.radius),c.visible=p!==null}const d=l.joints["index-finger-tip"],h=l.joints["thumb-tip"],f=d.position.distanceTo(h.position),m=.02,_=.005;l.inputState.pinching&&f>m+_?(l.inputState.pinching=!1,this.dispatchEvent({type:"pinchend",handedness:e.handedness,target:this})):!l.inputState.pinching&&f<=m-_&&(l.inputState.pinching=!0,this.dispatchEvent({type:"pinchstart",handedness:e.handedness,target:this}))}else u!==null&&e.gripSpace&&(s=t.getPose(e.gripSpace,n),s!==null&&(u.matrix.fromArray(s.transform.matrix),u.matrix.decompose(u.position,u.rotation,u.scale),u.matrixWorldNeedsUpdate=!0,s.linearVelocity?(u.hasLinearVelocity=!0,u.linearVelocity.copy(s.linearVelocity)):u.hasLinearVelocity=!1,s.angularVelocity?(u.hasAngularVelocity=!0,u.angularVelocity.copy(s.angularVelocity)):u.hasAngularVelocity=!1));a!==null&&(r=t.getPose(e.targetRaySpace,n),r===null&&s!==null&&(r=s),r!==null&&(a.matrix.fromArray(r.transform.matrix),a.matrix.decompose(a.position,a.rotation,a.scale),a.matrixWorldNeedsUpdate=!0,r.linearVelocity?(a.hasLinearVelocity=!0,a.linearVelocity.copy(r.linearVelocity)):a.hasLinearVelocity=!1,r.angularVelocity?(a.hasAngularVelocity=!0,a.angularVelocity.copy(r.angularVelocity)):a.hasAngularVelocity=!1,this.dispatchEvent(Qc)))}return a!==null&&(a.visible=r!==null),u!==null&&(u.visible=s!==null),l!==null&&(l.visible=o!==null),this}_getHandJoint(e,t){if(e.joints[t.jointName]===void 0){const n=new zn;n.matrixAutoUpdate=!1,n.visible=!1,e.joints[t.jointName]=n,e.add(n)}return e.joints[t.jointName]}}class eu extends Pt{constructor(){super(),this.isScene=!0,this.type="Scene",this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new fn,this.environmentIntensity=1,this.environmentRotation=new fn,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}copy(e,t){return super.copy(e,t),e.background!==null&&(this.background=e.background.clone()),e.environment!==null&&(this.environment=e.environment.clone()),e.fog!==null&&(this.fog=e.fog.clone()),this.backgroundBlurriness=e.backgroundBlurriness,this.backgroundIntensity=e.backgroundIntensity,this.backgroundRotation.copy(e.backgroundRotation),this.environmentIntensity=e.environmentIntensity,this.environmentRotation.copy(e.environmentRotation),e.overrideMaterial!==null&&(this.overrideMaterial=e.overrideMaterial.clone()),this.matrixAutoUpdate=e.matrixAutoUpdate,this}toJSON(e){const t=super.toJSON(e);return this.fog!==null&&(t.object.fog=this.fog.toJSON()),this.backgroundBlurriness>0&&(t.object.backgroundBlurriness=this.backgroundBlurriness),this.backgroundIntensity!==1&&(t.object.backgroundIntensity=this.backgroundIntensity),t.object.backgroundRotation=this.backgroundRotation.toArray(),this.environmentIntensity!==1&&(t.object.environmentIntensity=this.environmentIntensity),t.object.environmentRotation=this.environmentRotation.toArray(),t}}const Es=new B,tu=new B,nu=new Qe;class bn{constructor(e=new B(1,0,0),t=0){this.isPlane=!0,this.normal=e,this.constant=t}set(e,t){return this.normal.copy(e),this.constant=t,this}setComponents(e,t,n,r){return this.normal.set(e,t,n),this.constant=r,this}setFromNormalAndCoplanarPoint(e,t){return this.normal.copy(e),this.constant=-t.dot(this.normal),this}setFromCoplanarPoints(e,t,n){const r=Es.subVectors(n,t).cross(tu.subVectors(e,t)).normalize();return this.setFromNormalAndCoplanarPoint(r,e),this}copy(e){return this.normal.copy(e.normal),this.constant=e.constant,this}normalize(){const e=1/this.normal.length();return this.normal.multiplyScalar(e),this.constant*=e,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(e){return this.normal.dot(e)+this.constant}distanceToSphere(e){return this.distanceToPoint(e.center)-e.radius}projectPoint(e,t){return t.copy(e).addScaledVector(this.normal,-this.distanceToPoint(e))}intersectLine(e,t){const n=e.delta(Es),r=this.normal.dot(n);if(r===0)return this.distanceToPoint(e.start)===0?t.copy(e.start):null;const s=-(e.start.dot(this.normal)+this.constant)/r;return s<0||s>1?null:t.copy(e.start).addScaledVector(n,s)}intersectsLine(e){const t=this.distanceToPoint(e.start),n=this.distanceToPoint(e.end);return t<0&&n>0||n<0&&t>0}intersectsBox(e){return e.intersectsPlane(this)}intersectsSphere(e){return e.intersectsPlane(this)}coplanarPoint(e){return e.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(e,t){const n=t||nu.getNormalMatrix(e),r=this.coplanarPoint(Es).applyMatrix4(e),s=this.normal.applyMatrix3(n).normalize();return this.constant=-r.dot(s),this}translate(e){return this.constant-=e.dot(this.normal),this}equals(e){return e.normal.equals(this.normal)&&e.constant===this.constant}clone(){return new this.constructor().copy(this)}}const Kn=new Kr,iu=new Ye(.5,.5),wr=new B;class zo{constructor(e=new bn,t=new bn,n=new bn,r=new bn,s=new bn,o=new bn){this.planes=[e,t,n,r,s,o]}set(e,t,n,r,s,o){const a=this.planes;return a[0].copy(e),a[1].copy(t),a[2].copy(n),a[3].copy(r),a[4].copy(s),a[5].copy(o),this}copy(e){const t=this.planes;for(let n=0;n<6;n++)t[n].copy(e.planes[n]);return this}setFromProjectionMatrix(e,t=gn,n=!1){const r=this.planes,s=e.elements,o=s[0],a=s[1],u=s[2],l=s[3],d=s[4],h=s[5],f=s[6],m=s[7],_=s[8],v=s[9],p=s[10],c=s[11],A=s[12],S=s[13],M=s[14],C=s[15];if(r[0].setComponents(l-o,m-d,c-_,C-A).normalize(),r[1].setComponents(l+o,m+d,c+_,C+A).normalize(),r[2].setComponents(l+a,m+h,c+v,C+S).normalize(),r[3].setComponents(l-a,m-h,c-v,C-S).normalize(),n)r[4].setComponents(u,f,p,M).normalize(),r[5].setComponents(l-u,m-f,c-p,C-M).normalize();else if(r[4].setComponents(l-u,m-f,c-p,C-M).normalize(),t===gn)r[5].setComponents(l+u,m+f,c+p,C+M).normalize();else if(t===Xr)r[5].setComponents(u,f,p,M).normalize();else throw new Error("THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: "+t);return this}intersectsObject(e){if(e.boundingSphere!==void 0)e.boundingSphere===null&&e.computeBoundingSphere(),Kn.copy(e.boundingSphere).applyMatrix4(e.matrixWorld);else{const t=e.geometry;t.boundingSphere===null&&t.computeBoundingSphere(),Kn.copy(t.boundingSphere).applyMatrix4(e.matrixWorld)}return this.intersectsSphere(Kn)}intersectsSprite(e){Kn.center.set(0,0,0);const t=iu.distanceTo(e.center);return Kn.radius=.7071067811865476+t,Kn.applyMatrix4(e.matrixWorld),this.intersectsSphere(Kn)}intersectsSphere(e){const t=this.planes,n=e.center,r=-e.radius;for(let s=0;s<6;s++)if(t[s].distanceToPoint(n)<r)return!1;return!0}intersectsBox(e){const t=this.planes;for(let n=0;n<6;n++){const r=t[n];if(wr.x=r.normal.x>0?e.max.x:e.min.x,wr.y=r.normal.y>0?e.max.y:e.min.y,wr.z=r.normal.z>0?e.max.z:e.min.z,r.distanceToPoint(wr)<0)return!1}return!0}containsPoint(e){const t=this.planes;for(let n=0;n<6;n++)if(t[n].distanceToPoint(e)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}}class sr extends oi{constructor(e){super(),this.isLineBasicMaterial=!0,this.type="LineBasicMaterial",this.color=new je(16777215),this.map=null,this.linewidth=1,this.linecap="round",this.linejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.linewidth=e.linewidth,this.linecap=e.linecap,this.linejoin=e.linejoin,this.fog=e.fog,this}}const qr=new B,Yr=new B,ga=new gt,ji=new Zr,Rr=new Kr,Ts=new B,_a=new B;class Sl extends Pt{constructor(e=new yt,t=new sr){super(),this.isLine=!0,this.type="Line",this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}computeLineDistances(){const e=this.geometry;if(e.index===null){const t=e.attributes.position,n=[0];for(let r=1,s=t.count;r<s;r++)qr.fromBufferAttribute(t,r-1),Yr.fromBufferAttribute(t,r),n[r]=n[r-1],n[r]+=qr.distanceTo(Yr);e.setAttribute("lineDistance",new lt(n,1))}else console.warn("THREE.Line.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}raycast(e,t){const n=this.geometry,r=this.matrixWorld,s=e.params.Line.threshold,o=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),Rr.copy(n.boundingSphere),Rr.applyMatrix4(r),Rr.radius+=s,e.ray.intersectsSphere(Rr)===!1)return;ga.copy(r).invert(),ji.copy(e.ray).applyMatrix4(ga);const a=s/((this.scale.x+this.scale.y+this.scale.z)/3),u=a*a,l=this.isLineSegments?2:1,d=n.index,f=n.attributes.position;if(d!==null){const m=Math.max(0,o.start),_=Math.min(d.count,o.start+o.count);for(let v=m,p=_-1;v<p;v+=l){const c=d.getX(v),A=d.getX(v+1),S=Cr(this,e,ji,u,c,A,v);S&&t.push(S)}if(this.isLineLoop){const v=d.getX(_-1),p=d.getX(m),c=Cr(this,e,ji,u,v,p,_-1);c&&t.push(c)}}else{const m=Math.max(0,o.start),_=Math.min(f.count,o.start+o.count);for(let v=m,p=_-1;v<p;v+=l){const c=Cr(this,e,ji,u,v,v+1,v);c&&t.push(c)}if(this.isLineLoop){const v=Cr(this,e,ji,u,_-1,m,_-1);v&&t.push(v)}}}updateMorphTargets(){const t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){const r=t[n[0]];if(r!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let s=0,o=r.length;s<o;s++){const a=r[s].name||String(s);this.morphTargetInfluences.push(0),this.morphTargetDictionary[a]=s}}}}}function Cr(i,e,t,n,r,s,o){const a=i.geometry.attributes.position;if(qr.fromBufferAttribute(a,r),Yr.fromBufferAttribute(a,s),t.distanceSqToSegment(qr,Yr,Ts,_a)>n)return;Ts.applyMatrix4(i.matrixWorld);const l=e.ray.origin.distanceTo(Ts);if(!(l<e.near||l>e.far))return{distance:l,point:_a.clone().applyMatrix4(i.matrixWorld),index:o,face:null,faceIndex:null,barycoord:null,object:i}}const va=new B,xa=new B;class Ho extends Sl{constructor(e,t){super(e,t),this.isLineSegments=!0,this.type="LineSegments"}computeLineDistances(){const e=this.geometry;if(e.index===null){const t=e.attributes.position,n=[];for(let r=0,s=t.count;r<s;r+=2)va.fromBufferAttribute(t,r),xa.fromBufferAttribute(t,r+1),n[r]=r===0?0:n[r-1],n[r+1]=n[r]+va.distanceTo(xa);e.setAttribute("lineDistance",new lt(n,1))}else console.warn("THREE.LineSegments.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}}class yl extends Ot{constructor(e,t,n=ni,r,s,o,a=Zt,u=Zt,l,d=nr,h=1){if(d!==nr&&d!==ir)throw new Error("DepthTexture format must be either THREE.DepthFormat or THREE.DepthStencilFormat");const f={width:e,height:t,depth:h};super(f,r,s,o,a,u,d,n,l),this.isDepthTexture=!0,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(e){return super.copy(e),this.source=new Fo(Object.assign({},e.image)),this.compareFunction=e.compareFunction,this}toJSON(e){const t=super.toJSON(e);return this.compareFunction!==null&&(t.compareFunction=this.compareFunction),t}}const Pr=new B,Dr=new B,bs=new B,Lr=new on;class ru extends yt{constructor(e=null,t=1){if(super(),this.type="EdgesGeometry",this.parameters={geometry:e,thresholdAngle:t},e!==null){const r=Math.pow(10,4),s=Math.cos(Zi*t),o=e.getIndex(),a=e.getAttribute("position"),u=o?o.count:a.count,l=[0,0,0],d=["a","b","c"],h=new Array(3),f={},m=[];for(let _=0;_<u;_+=3){o?(l[0]=o.getX(_),l[1]=o.getX(_+1),l[2]=o.getX(_+2)):(l[0]=_,l[1]=_+1,l[2]=_+2);const{a:v,b:p,c}=Lr;if(v.fromBufferAttribute(a,l[0]),p.fromBufferAttribute(a,l[1]),c.fromBufferAttribute(a,l[2]),Lr.getNormal(bs),h[0]=`${Math.round(v.x*r)},${Math.round(v.y*r)},${Math.round(v.z*r)}`,h[1]=`${Math.round(p.x*r)},${Math.round(p.y*r)},${Math.round(p.z*r)}`,h[2]=`${Math.round(c.x*r)},${Math.round(c.y*r)},${Math.round(c.z*r)}`,!(h[0]===h[1]||h[1]===h[2]||h[2]===h[0]))for(let A=0;A<3;A++){const S=(A+1)%3,M=h[A],C=h[S],R=Lr[d[A]],P=Lr[d[S]],I=`${M}_${C}`,y=`${C}_${M}`;y in f&&f[y]?(bs.dot(f[y].normal)<=s&&(m.push(R.x,R.y,R.z),m.push(P.x,P.y,P.z)),f[y]=null):I in f||(f[I]={index0:l[A],index1:l[S],normal:bs.clone()})}}for(const _ in f)if(f[_]){const{index0:v,index1:p}=f[_];Pr.fromBufferAttribute(a,v),Dr.fromBufferAttribute(a,p),m.push(Pr.x,Pr.y,Pr.z),m.push(Dr.x,Dr.y,Dr.z)}this.setAttribute("position",new lt(m,3))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}}class $r extends yt{constructor(e=1,t=1,n=1,r=1){super(),this.type="PlaneGeometry",this.parameters={width:e,height:t,widthSegments:n,heightSegments:r};const s=e/2,o=t/2,a=Math.floor(n),u=Math.floor(r),l=a+1,d=u+1,h=e/a,f=t/u,m=[],_=[],v=[],p=[];for(let c=0;c<d;c++){const A=c*f-o;for(let S=0;S<l;S++){const M=S*h-s;_.push(M,-A,0),v.push(0,0,1),p.push(S/a),p.push(1-c/u)}}for(let c=0;c<u;c++)for(let A=0;A<a;A++){const S=A+l*c,M=A+l*(c+1),C=A+1+l*(c+1),R=A+1+l*c;m.push(S,M,R),m.push(M,C,R)}this.setIndex(m),this.setAttribute("position",new lt(_,3)),this.setAttribute("normal",new lt(v,3)),this.setAttribute("uv",new lt(p,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new $r(e.width,e.height,e.widthSegments,e.heightSegments)}}class ko extends yt{constructor(e=1,t=32,n=16,r=0,s=Math.PI*2,o=0,a=Math.PI){super(),this.type="SphereGeometry",this.parameters={radius:e,widthSegments:t,heightSegments:n,phiStart:r,phiLength:s,thetaStart:o,thetaLength:a},t=Math.max(3,Math.floor(t)),n=Math.max(2,Math.floor(n));const u=Math.min(o+a,Math.PI);let l=0;const d=[],h=new B,f=new B,m=[],_=[],v=[],p=[];for(let c=0;c<=n;c++){const A=[],S=c/n;let M=0;c===0&&o===0?M=.5/t:c===n&&u===Math.PI&&(M=-.5/t);for(let C=0;C<=t;C++){const R=C/t;h.x=-e*Math.cos(r+R*s)*Math.sin(o+S*a),h.y=e*Math.cos(o+S*a),h.z=e*Math.sin(r+R*s)*Math.sin(o+S*a),_.push(h.x,h.y,h.z),f.copy(h).normalize(),v.push(f.x,f.y,f.z),p.push(R+M,1-S),A.push(l++)}d.push(A)}for(let c=0;c<n;c++)for(let A=0;A<t;A++){const S=d[c][A+1],M=d[c][A],C=d[c+1][A],R=d[c+1][A+1];(c!==0||o>0)&&m.push(S,M,R),(c!==n-1||u<Math.PI)&&m.push(M,C,R)}this.setIndex(m),this.setAttribute("position",new lt(_,3)),this.setAttribute("normal",new lt(v,3)),this.setAttribute("uv",new lt(p,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new ko(e.radius,e.widthSegments,e.heightSegments,e.phiStart,e.phiLength,e.thetaStart,e.thetaLength)}}class El extends oi{constructor(e){super(),this.isMeshStandardMaterial=!0,this.type="MeshStandardMaterial",this.defines={STANDARD:""},this.color=new je(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new je(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=No,this.normalScale=new Ye(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new fn,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.defines={STANDARD:""},this.color.copy(e.color),this.roughness=e.roughness,this.metalness=e.metalness,this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.roughnessMap=e.roughnessMap,this.metalnessMap=e.metalnessMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.envMapIntensity=e.envMapIntensity,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}}class Ur extends oi{constructor(e){super(),this.isMeshPhongMaterial=!0,this.type="MeshPhongMaterial",this.color=new je(16777215),this.specular=new je(1118481),this.shininess=30,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new je(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=No,this.normalScale=new Ye(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new fn,this.combine=Ro,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.specular.copy(e.specular),this.shininess=e.shininess,this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}}class su extends oi{constructor(e){super(),this.isMeshDepthMaterial=!0,this.type="MeshDepthMaterial",this.depthPacking=gc,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(e)}copy(e){return super.copy(e),this.depthPacking=e.depthPacking,this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this}}class ou extends oi{constructor(e){super(),this.isMeshDistanceMaterial=!0,this.type="MeshDistanceMaterial",this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(e)}copy(e){return super.copy(e),this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this}}const $i={enabled:!1,files:{},add:function(i,e){this.enabled!==!1&&(this.files[i]=e)},get:function(i){if(this.enabled!==!1)return this.files[i]},remove:function(i){delete this.files[i]},clear:function(){this.files={}}};class au{constructor(e,t,n){const r=this;let s=!1,o=0,a=0,u;const l=[];this.onStart=void 0,this.onLoad=e,this.onProgress=t,this.onError=n,this.abortController=new AbortController,this.itemStart=function(d){a++,s===!1&&r.onStart!==void 0&&r.onStart(d,o,a),s=!0},this.itemEnd=function(d){o++,r.onProgress!==void 0&&r.onProgress(d,o,a),o===a&&(s=!1,r.onLoad!==void 0&&r.onLoad())},this.itemError=function(d){r.onError!==void 0&&r.onError(d)},this.resolveURL=function(d){return u?u(d):d},this.setURLModifier=function(d){return u=d,this},this.addHandler=function(d,h){return l.push(d,h),this},this.removeHandler=function(d){const h=l.indexOf(d);return h!==-1&&l.splice(h,2),this},this.getHandler=function(d){for(let h=0,f=l.length;h<f;h+=2){const m=l[h],_=l[h+1];if(m.global&&(m.lastIndex=0),m.test(d))return _}return null},this.abort=function(){return this.abortController.abort(),this.abortController=new AbortController,this}}}const lu=new au;class Wn{constructor(e){this.manager=e!==void 0?e:lu,this.crossOrigin="anonymous",this.withCredentials=!1,this.path="",this.resourcePath="",this.requestHeader={}}load(){}loadAsync(e,t){const n=this;return new Promise(function(r,s){n.load(e,r,t,s)})}parse(){}setCrossOrigin(e){return this.crossOrigin=e,this}setWithCredentials(e){return this.withCredentials=e,this}setPath(e){return this.path=e,this}setResourcePath(e){return this.resourcePath=e,this}setRequestHeader(e){return this.requestHeader=e,this}abort(){return this}}Wn.DEFAULT_MATERIAL_NAME="__DEFAULT";const En={};class cu extends Error{constructor(e,t){super(e),this.response=t}}class Vo extends Wn{constructor(e){super(e),this.mimeType="",this.responseType="",this._abortController=new AbortController}load(e,t,n,r){e===void 0&&(e=""),this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);const s=$i.get(`file:${e}`);if(s!==void 0)return this.manager.itemStart(e),setTimeout(()=>{t&&t(s),this.manager.itemEnd(e)},0),s;if(En[e]!==void 0){En[e].push({onLoad:t,onProgress:n,onError:r});return}En[e]=[],En[e].push({onLoad:t,onProgress:n,onError:r});const o=new Request(e,{headers:new Headers(this.requestHeader),credentials:this.withCredentials?"include":"same-origin",signal:typeof AbortSignal.any=="function"?AbortSignal.any([this._abortController.signal,this.manager.abortController.signal]):this._abortController.signal}),a=this.mimeType,u=this.responseType;fetch(o).then(l=>{if(l.status===200||l.status===0){if(l.status===0&&console.warn("THREE.FileLoader: HTTP Status 0 received."),typeof ReadableStream>"u"||l.body===void 0||l.body.getReader===void 0)return l;const d=En[e],h=l.body.getReader(),f=l.headers.get("X-File-Size")||l.headers.get("Content-Length"),m=f?parseInt(f):0,_=m!==0;let v=0;const p=new ReadableStream({start(c){A();function A(){h.read().then(({done:S,value:M})=>{if(S)c.close();else{v+=M.byteLength;const C=new ProgressEvent("progress",{lengthComputable:_,loaded:v,total:m});for(let R=0,P=d.length;R<P;R++){const I=d[R];I.onProgress&&I.onProgress(C)}c.enqueue(M),A()}},S=>{c.error(S)})}}});return new Response(p)}else throw new cu(`fetch for "${l.url}" responded with ${l.status}: ${l.statusText}`,l)}).then(l=>{switch(u){case"arraybuffer":return l.arrayBuffer();case"blob":return l.blob();case"document":return l.text().then(d=>new DOMParser().parseFromString(d,a));case"json":return l.json();default:if(a==="")return l.text();{const h=/charset="?([^;"\s]*)"?/i.exec(a),f=h&&h[1]?h[1].toLowerCase():void 0,m=new TextDecoder(f);return l.arrayBuffer().then(_=>m.decode(_))}}}).then(l=>{$i.add(`file:${e}`,l);const d=En[e];delete En[e];for(let h=0,f=d.length;h<f;h++){const m=d[h];m.onLoad&&m.onLoad(l)}}).catch(l=>{const d=En[e];if(d===void 0)throw this.manager.itemError(e),l;delete En[e];for(let h=0,f=d.length;h<f;h++){const m=d[h];m.onError&&m.onError(l)}this.manager.itemError(e)}).finally(()=>{this.manager.itemEnd(e)}),this.manager.itemStart(e)}setResponseType(e){return this.responseType=e,this}setMimeType(e){return this.mimeType=e,this}abort(){return this._abortController.abort(),this._abortController=new AbortController,this}}const Ti=new WeakMap;class uu extends Wn{constructor(e){super(e)}load(e,t,n,r){this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);const s=this,o=$i.get(`image:${e}`);if(o!==void 0){if(o.complete===!0)s.manager.itemStart(e),setTimeout(function(){t&&t(o),s.manager.itemEnd(e)},0);else{let h=Ti.get(o);h===void 0&&(h=[],Ti.set(o,h)),h.push({onLoad:t,onError:r})}return o}const a=rr("img");function u(){d(),t&&t(this);const h=Ti.get(this)||[];for(let f=0;f<h.length;f++){const m=h[f];m.onLoad&&m.onLoad(this)}Ti.delete(this),s.manager.itemEnd(e)}function l(h){d(),r&&r(h),$i.remove(`image:${e}`);const f=Ti.get(this)||[];for(let m=0;m<f.length;m++){const _=f[m];_.onError&&_.onError(h)}Ti.delete(this),s.manager.itemError(e),s.manager.itemEnd(e)}function d(){a.removeEventListener("load",u,!1),a.removeEventListener("error",l,!1)}return a.addEventListener("load",u,!1),a.addEventListener("error",l,!1),e.slice(0,5)!=="data:"&&this.crossOrigin!==void 0&&(a.crossOrigin=this.crossOrigin),$i.add(`image:${e}`,a),s.manager.itemStart(e),a.src=e,a}}class hu extends Wn{constructor(e){super(e)}load(e,t,n,r){const s=new Ot,o=new uu(this.manager);return o.setCrossOrigin(this.crossOrigin),o.setPath(this.path),o.load(e,function(a){s.image=a,s.needsUpdate=!0,t!==void 0&&t(s)},n,r),s}}class Tl extends Pt{constructor(e,t=1){super(),this.isLight=!0,this.type="Light",this.color=new je(e),this.intensity=t}dispose(){}copy(e,t){return super.copy(e,t),this.color.copy(e.color),this.intensity=e.intensity,this}toJSON(e){const t=super.toJSON(e);return t.object.color=this.color.getHex(),t.object.intensity=this.intensity,this.groundColor!==void 0&&(t.object.groundColor=this.groundColor.getHex()),this.distance!==void 0&&(t.object.distance=this.distance),this.angle!==void 0&&(t.object.angle=this.angle),this.decay!==void 0&&(t.object.decay=this.decay),this.penumbra!==void 0&&(t.object.penumbra=this.penumbra),this.shadow!==void 0&&(t.object.shadow=this.shadow.toJSON()),this.target!==void 0&&(t.object.target=this.target.uuid),t}}class du extends Tl{constructor(e,t,n){super(e,n),this.isHemisphereLight=!0,this.type="HemisphereLight",this.position.copy(Pt.DEFAULT_UP),this.updateMatrix(),this.groundColor=new je(t)}copy(e,t){return super.copy(e,t),this.groundColor.copy(e.groundColor),this}}const As=new gt,Ma=new B,Sa=new B;class fu{constructor(e){this.camera=e,this.intensity=1,this.bias=0,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new Ye(512,512),this.mapType=_n,this.map=null,this.mapPass=null,this.matrix=new gt,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new zo,this._frameExtents=new Ye(1,1),this._viewportCount=1,this._viewports=[new Mt(0,0,1,1)]}getViewportCount(){return this._viewportCount}getFrustum(){return this._frustum}updateMatrices(e){const t=this.camera,n=this.matrix;Ma.setFromMatrixPosition(e.matrixWorld),t.position.copy(Ma),Sa.setFromMatrixPosition(e.target.matrixWorld),t.lookAt(Sa),t.updateMatrixWorld(),As.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),this._frustum.setFromProjectionMatrix(As,t.coordinateSystem,t.reversedDepth),t.reversedDepth?n.set(.5,0,0,.5,0,.5,0,.5,0,0,1,0,0,0,0,1):n.set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1),n.multiply(As)}getViewport(e){return this._viewports[e]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(e){return this.camera=e.camera.clone(),this.intensity=e.intensity,this.bias=e.bias,this.radius=e.radius,this.autoUpdate=e.autoUpdate,this.needsUpdate=e.needsUpdate,this.normalBias=e.normalBias,this.blurSamples=e.blurSamples,this.mapSize.copy(e.mapSize),this}clone(){return new this.constructor().copy(this)}toJSON(){const e={};return this.intensity!==1&&(e.intensity=this.intensity),this.bias!==0&&(e.bias=this.bias),this.normalBias!==0&&(e.normalBias=this.normalBias),this.radius!==1&&(e.radius=this.radius),(this.mapSize.x!==512||this.mapSize.y!==512)&&(e.mapSize=this.mapSize.toArray()),e.camera=this.camera.toJSON(!1).object,delete e.camera.matrix,e}}class bl extends xl{constructor(e=-1,t=1,n=1,r=-1,s=.1,o=2e3){super(),this.isOrthographicCamera=!0,this.type="OrthographicCamera",this.zoom=1,this.view=null,this.left=e,this.right=t,this.top=n,this.bottom=r,this.near=s,this.far=o,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.left=e.left,this.right=e.right,this.top=e.top,this.bottom=e.bottom,this.near=e.near,this.far=e.far,this.zoom=e.zoom,this.view=e.view===null?null:Object.assign({},e.view),this}setViewOffset(e,t,n,r,s,o){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=s,this.view.height=o,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){const e=(this.right-this.left)/(2*this.zoom),t=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,r=(this.top+this.bottom)/2;let s=n-e,o=n+e,a=r+t,u=r-t;if(this.view!==null&&this.view.enabled){const l=(this.right-this.left)/this.view.fullWidth/this.zoom,d=(this.top-this.bottom)/this.view.fullHeight/this.zoom;s+=l*this.view.offsetX,o=s+l*this.view.width,a-=d*this.view.offsetY,u=a-d*this.view.height}this.projectionMatrix.makeOrthographic(s,o,a,u,this.near,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){const t=super.toJSON(e);return t.object.zoom=this.zoom,t.object.left=this.left,t.object.right=this.right,t.object.top=this.top,t.object.bottom=this.bottom,t.object.near=this.near,t.object.far=this.far,this.view!==null&&(t.object.view=Object.assign({},this.view)),t}}class pu extends fu{constructor(){super(new bl(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}}class ya extends Tl{constructor(e,t){super(e,t),this.isDirectionalLight=!0,this.type="DirectionalLight",this.position.copy(Pt.DEFAULT_UP),this.updateMatrix(),this.target=new Pt,this.shadow=new pu}dispose(){this.shadow.dispose()}copy(e){return super.copy(e),this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}}class mu extends sn{constructor(e=[]){super(),this.isArrayCamera=!0,this.isMultiViewCamera=!1,this.cameras=e}}const Ea=new gt;class gu{constructor(e,t,n=0,r=1/0){this.ray=new Zr(e,t),this.near=n,this.far=r,this.camera=null,this.layers=new Oo,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(e,t){this.ray.set(e,t)}setFromCamera(e,t){t.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(e.x,e.y,.5).unproject(t).sub(this.ray.origin).normalize(),this.camera=t):t.isOrthographicCamera?(this.ray.origin.set(e.x,e.y,(t.near+t.far)/(t.near-t.far)).unproject(t),this.ray.direction.set(0,0,-1).transformDirection(t.matrixWorld),this.camera=t):console.error("THREE.Raycaster: Unsupported camera type: "+t.type)}setFromXRController(e){return Ea.identity().extractRotation(e.matrixWorld),this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(Ea),this}intersectObject(e,t=!0,n=[]){return Eo(e,this,n,t),n.sort(Ta),n}intersectObjects(e,t=!0,n=[]){for(let r=0,s=e.length;r<s;r++)Eo(e[r],this,n,t);return n.sort(Ta),n}}function Ta(i,e){return i.distance-e.distance}function Eo(i,e,t,n){let r=!0;if(i.layers.test(e.layers)&&i.raycast(e,t)===!1&&(r=!1),r===!0&&n===!0){const s=i.children;for(let o=0,a=s.length;o<a;o++)Eo(s[o],e,t,!0)}}class ba{constructor(e=1,t=0,n=0){this.radius=e,this.phi=t,this.theta=n}set(e,t,n){return this.radius=e,this.phi=t,this.theta=n,this}copy(e){return this.radius=e.radius,this.phi=e.phi,this.theta=e.theta,this}makeSafe(){return this.phi=rt(this.phi,1e-6,Math.PI-1e-6),this}setFromVector3(e){return this.setFromCartesianCoords(e.x,e.y,e.z)}setFromCartesianCoords(e,t,n){return this.radius=Math.sqrt(e*e+t*t+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(e,n),this.phi=Math.acos(rt(t/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}}class _u extends Ho{constructor(e=10,t=10,n=4473924,r=8947848){n=new je(n),r=new je(r);const s=t/2,o=e/t,a=e/2,u=[],l=[];for(let f=0,m=0,_=-a;f<=t;f++,_+=o){u.push(-a,0,_,a,0,_),u.push(_,0,-a,_,0,a);const v=f===s?n:r;v.toArray(l,m),m+=3,v.toArray(l,m),m+=3,v.toArray(l,m),m+=3,v.toArray(l,m),m+=3}const d=new yt;d.setAttribute("position",new lt(u,3)),d.setAttribute("color",new lt(l,3));const h=new sr({vertexColors:!0,toneMapped:!1});super(d,h),this.type="GridHelper"}dispose(){this.geometry.dispose(),this.material.dispose()}}class vu extends Ho{constructor(e=1){const t=[0,0,0,e,0,0,0,0,0,0,e,0,0,0,0,0,0,e],n=[1,0,0,1,.6,0,0,1,0,.6,1,0,0,0,1,0,.6,1],r=new yt;r.setAttribute("position",new lt(t,3)),r.setAttribute("color",new lt(n,3));const s=new sr({vertexColors:!0,toneMapped:!1});super(r,s),this.type="AxesHelper"}setColors(e,t,n){const r=new je,s=this.geometry.attributes.color.array;return r.set(e),r.toArray(s,0),r.toArray(s,3),r.set(t),r.toArray(s,6),r.toArray(s,9),r.set(n),r.toArray(s,12),r.toArray(s,15),this.geometry.attributes.color.needsUpdate=!0,this}dispose(){this.geometry.dispose(),this.material.dispose()}}class xu extends si{constructor(e,t=null){super(),this.object=e,this.domElement=t,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(e){if(e===void 0){console.warn("THREE.Controls: connect() now requires an element.");return}this.domElement!==null&&this.disconnect(),this.domElement=e}disconnect(){}dispose(){}update(){}}function Aa(i,e,t,n){const r=Mu(n);switch(t){case al:return i*e;case cl:return i*e/r.components*r.byteLength;case Lo:return i*e/r.components*r.byteLength;case ul:return i*e*2/r.components*r.byteLength;case Uo:return i*e*2/r.components*r.byteLength;case ll:return i*e*3/r.components*r.byteLength;case dn:return i*e*4/r.components*r.byteLength;case Io:return i*e*4/r.components*r.byteLength;case Br:case zr:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case Hr:case kr:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case Zs:case Js:return Math.max(i,16)*Math.max(e,8)/4;case Ks:case $s:return Math.max(i,8)*Math.max(e,8)/2;case Qs:case eo:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case to:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case no:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case io:return Math.floor((i+4)/5)*Math.floor((e+3)/4)*16;case ro:return Math.floor((i+4)/5)*Math.floor((e+4)/5)*16;case so:return Math.floor((i+5)/6)*Math.floor((e+4)/5)*16;case oo:return Math.floor((i+5)/6)*Math.floor((e+5)/6)*16;case ao:return Math.floor((i+7)/8)*Math.floor((e+4)/5)*16;case lo:return Math.floor((i+7)/8)*Math.floor((e+5)/6)*16;case co:return Math.floor((i+7)/8)*Math.floor((e+7)/8)*16;case uo:return Math.floor((i+9)/10)*Math.floor((e+4)/5)*16;case ho:return Math.floor((i+9)/10)*Math.floor((e+5)/6)*16;case fo:return Math.floor((i+9)/10)*Math.floor((e+7)/8)*16;case po:return Math.floor((i+9)/10)*Math.floor((e+9)/10)*16;case mo:return Math.floor((i+11)/12)*Math.floor((e+9)/10)*16;case go:return Math.floor((i+11)/12)*Math.floor((e+11)/12)*16;case Vr:case _o:case vo:return Math.ceil(i/4)*Math.ceil(e/4)*16;case hl:case xo:return Math.ceil(i/4)*Math.ceil(e/4)*8;case Mo:case So:return Math.ceil(i/4)*Math.ceil(e/4)*16}throw new Error(`Unable to determine texture byte length for ${t} format.`)}function Mu(i){switch(i){case _n:case rl:return{byteLength:1,components:1};case er:case sl:case or:return{byteLength:2,components:1};case Po:case Do:return{byteLength:2,components:4};case ni:case Co:case Cn:return{byteLength:4,components:1};case ol:return{byteLength:4,components:3}}throw new Error(`Unknown texture type ${i}.`)}typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("register",{detail:{revision:wo}}));typeof window<"u"&&(window.__THREE__?console.warn("WARNING: Multiple instances of Three.js being imported."):window.__THREE__=wo);/**
 * @license
 * Copyright 2010-2025 Three.js Authors
 * SPDX-License-Identifier: MIT
 */function Al(){let i=null,e=!1,t=null,n=null;function r(s,o){t(s,o),n=i.requestAnimationFrame(r)}return{start:function(){e!==!0&&t!==null&&(n=i.requestAnimationFrame(r),e=!0)},stop:function(){i.cancelAnimationFrame(n),e=!1},setAnimationLoop:function(s){t=s},setContext:function(s){i=s}}}function Su(i){const e=new WeakMap;function t(a,u){const l=a.array,d=a.usage,h=l.byteLength,f=i.createBuffer();i.bindBuffer(u,f),i.bufferData(u,l,d),a.onUploadCallback();let m;if(l instanceof Float32Array)m=i.FLOAT;else if(typeof Float16Array<"u"&&l instanceof Float16Array)m=i.HALF_FLOAT;else if(l instanceof Uint16Array)a.isFloat16BufferAttribute?m=i.HALF_FLOAT:m=i.UNSIGNED_SHORT;else if(l instanceof Int16Array)m=i.SHORT;else if(l instanceof Uint32Array)m=i.UNSIGNED_INT;else if(l instanceof Int32Array)m=i.INT;else if(l instanceof Int8Array)m=i.BYTE;else if(l instanceof Uint8Array)m=i.UNSIGNED_BYTE;else if(l instanceof Uint8ClampedArray)m=i.UNSIGNED_BYTE;else throw new Error("THREE.WebGLAttributes: Unsupported buffer data format: "+l);return{buffer:f,type:m,bytesPerElement:l.BYTES_PER_ELEMENT,version:a.version,size:h}}function n(a,u,l){const d=u.array,h=u.updateRanges;if(i.bindBuffer(l,a),h.length===0)i.bufferSubData(l,0,d);else{h.sort((m,_)=>m.start-_.start);let f=0;for(let m=1;m<h.length;m++){const _=h[f],v=h[m];v.start<=_.start+_.count+1?_.count=Math.max(_.count,v.start+v.count-_.start):(++f,h[f]=v)}h.length=f+1;for(let m=0,_=h.length;m<_;m++){const v=h[m];i.bufferSubData(l,v.start*d.BYTES_PER_ELEMENT,d,v.start,v.count)}u.clearUpdateRanges()}u.onUploadCallback()}function r(a){return a.isInterleavedBufferAttribute&&(a=a.data),e.get(a)}function s(a){a.isInterleavedBufferAttribute&&(a=a.data);const u=e.get(a);u&&(i.deleteBuffer(u.buffer),e.delete(a))}function o(a,u){if(a.isInterleavedBufferAttribute&&(a=a.data),a.isGLBufferAttribute){const d=e.get(a);(!d||d.version<a.version)&&e.set(a,{buffer:a.buffer,type:a.type,bytesPerElement:a.elementSize,version:a.version});return}const l=e.get(a);if(l===void 0)e.set(a,t(a,u));else if(l.version<a.version){if(l.size!==a.array.byteLength)throw new Error("THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.");n(l.buffer,a,u),l.version=a.version}}return{get:r,remove:s,update:o}}var yu=`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,Eu=`#ifdef USE_ALPHAHASH
	const float ALPHA_HASH_SCALE = 0.05;
	float hash2D( vec2 value ) {
		return fract( 1.0e4 * sin( 17.0 * value.x + 0.1 * value.y ) * ( 0.1 + abs( sin( 13.0 * value.y + value.x ) ) ) );
	}
	float hash3D( vec3 value ) {
		return hash2D( vec2( hash2D( value.xy ), value.z ) );
	}
	float getAlphaHashThreshold( vec3 position ) {
		float maxDeriv = max(
			length( dFdx( position.xyz ) ),
			length( dFdy( position.xyz ) )
		);
		float pixScale = 1.0 / ( ALPHA_HASH_SCALE * maxDeriv );
		vec2 pixScales = vec2(
			exp2( floor( log2( pixScale ) ) ),
			exp2( ceil( log2( pixScale ) ) )
		);
		vec2 alpha = vec2(
			hash3D( floor( pixScales.x * position.xyz ) ),
			hash3D( floor( pixScales.y * position.xyz ) )
		);
		float lerpFactor = fract( log2( pixScale ) );
		float x = ( 1.0 - lerpFactor ) * alpha.x + lerpFactor * alpha.y;
		float a = min( lerpFactor, 1.0 - lerpFactor );
		vec3 cases = vec3(
			x * x / ( 2.0 * a * ( 1.0 - a ) ),
			( x - 0.5 * a ) / ( 1.0 - a ),
			1.0 - ( ( 1.0 - x ) * ( 1.0 - x ) / ( 2.0 * a * ( 1.0 - a ) ) )
		);
		float threshold = ( x < ( 1.0 - a ) )
			? ( ( x < a ) ? cases.x : cases.y )
			: cases.z;
		return clamp( threshold , 1.0e-6, 1.0 );
	}
#endif`,Tu=`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,bu=`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Au=`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,wu=`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,Ru=`#ifdef USE_AOMAP
	float ambientOcclusion = ( texture2D( aoMap, vAoMapUv ).r - 1.0 ) * aoMapIntensity + 1.0;
	reflectedLight.indirectDiffuse *= ambientOcclusion;
	#if defined( USE_CLEARCOAT ) 
		clearcoatSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_SHEEN ) 
		sheenSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD )
		float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
		reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
	#endif
#endif`,Cu=`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,Pu=`#ifdef USE_BATCHING
	#if ! defined( GL_ANGLE_multi_draw )
	#define gl_DrawID _gl_DrawID
	uniform int _gl_DrawID;
	#endif
	uniform highp sampler2D batchingTexture;
	uniform highp usampler2D batchingIdTexture;
	mat4 getBatchingMatrix( const in float i ) {
		int size = textureSize( batchingTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( batchingTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( batchingTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( batchingTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( batchingTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
	float getIndirectIndex( const in int i ) {
		int size = textureSize( batchingIdTexture, 0 ).x;
		int x = i % size;
		int y = i / size;
		return float( texelFetch( batchingIdTexture, ivec2( x, y ), 0 ).r );
	}
#endif
#ifdef USE_BATCHING_COLOR
	uniform sampler2D batchingColorTexture;
	vec3 getBatchingColor( const in float i ) {
		int size = textureSize( batchingColorTexture, 0 ).x;
		int j = int( i );
		int x = j % size;
		int y = j / size;
		return texelFetch( batchingColorTexture, ivec2( x, y ), 0 ).rgb;
	}
#endif`,Du=`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,Lu=`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,Uu=`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,Iu=`float G_BlinnPhong_Implicit( ) {
	return 0.25;
}
float D_BlinnPhong( const in float shininess, const in float dotNH ) {
	return RECIPROCAL_PI * ( shininess * 0.5 + 1.0 ) * pow( dotNH, shininess );
}
vec3 BRDF_BlinnPhong( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in vec3 specularColor, const in float shininess ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( specularColor, 1.0, dotVH );
	float G = G_BlinnPhong_Implicit( );
	float D = D_BlinnPhong( shininess, dotNH );
	return F * ( G * D );
} // validated`,Nu=`#ifdef USE_IRIDESCENCE
	const mat3 XYZ_TO_REC709 = mat3(
		 3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);
	vec3 Fresnel0ToIor( vec3 fresnel0 ) {
		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );
	}
	vec3 IorToFresnel0( vec3 transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );
	}
	float IorToFresnel0( float transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ));
	}
	vec3 evalSensitivity( float OPD, vec3 shift ) {
		float phase = 2.0 * PI * OPD * 1.0e-9;
		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );
		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - pow2( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * pow2( phase ) );
		xyz /= 1.0685e-7;
		vec3 rgb = XYZ_TO_REC709 * xyz;
		return rgb;
	}
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {
		vec3 I;
		float iridescenceIOR = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );
		float sinTheta2Sq = pow2( outsideIOR / iridescenceIOR ) * ( 1.0 - pow2( cosTheta1 ) );
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {
			return vec3( 1.0 );
		}
		float cosTheta2 = sqrt( cosTheta2Sq );
		float R0 = IorToFresnel0( iridescenceIOR, outsideIOR );
		float R12 = F_Schlick( R0, 1.0, cosTheta1 );
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIOR < outsideIOR ) phi12 = PI;
		float phi21 = PI - phi12;
		vec3 baseIOR = Fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) );		vec3 R1 = IorToFresnel0( baseIOR, iridescenceIOR );
		vec3 R23 = F_Schlick( R1, 1.0, cosTheta2 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[ 0 ] < iridescenceIOR ) phi23[ 0 ] = PI;
		if ( baseIOR[ 1 ] < iridescenceIOR ) phi23[ 1 ] = PI;
		if ( baseIOR[ 2 ] < iridescenceIOR ) phi23[ 2 ] = PI;
		float OPD = 2.0 * iridescenceIOR * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = pow2( T121 ) * R23 / ( vec3( 1.0 ) - R123 );
		vec3 C0 = R12 + Rs;
		I = C0;
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {
			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;
		}
		return max( I, vec3( 0.0 ) );
	}
#endif`,Fu=`#ifdef USE_BUMPMAP
	uniform sampler2D bumpMap;
	uniform float bumpScale;
	vec2 dHdxy_fwd() {
		vec2 dSTdx = dFdx( vBumpMapUv );
		vec2 dSTdy = dFdy( vBumpMapUv );
		float Hll = bumpScale * texture2D( bumpMap, vBumpMapUv ).x;
		float dBx = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdx ).x - Hll;
		float dBy = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdy ).x - Hll;
		return vec2( dBx, dBy );
	}
	vec3 perturbNormalArb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDirection ) {
		vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
		vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
		vec3 vN = surf_norm;
		vec3 R1 = cross( vSigmaY, vN );
		vec3 R2 = cross( vN, vSigmaX );
		float fDet = dot( vSigmaX, R1 ) * faceDirection;
		vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
		return normalize( abs( fDet ) * surf_norm - vGrad );
	}
#endif`,Ou=`#if NUM_CLIPPING_PLANES > 0
	vec4 plane;
	#ifdef ALPHA_TO_COVERAGE
		float distanceToPlane, distanceGradient;
		float clipOpacity = 1.0;
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
			distanceGradient = fwidth( distanceToPlane ) / 2.0;
			clipOpacity *= smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			if ( clipOpacity == 0.0 ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			float unionClipOpacity = 1.0;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
				distanceGradient = fwidth( distanceToPlane ) / 2.0;
				unionClipOpacity *= 1.0 - smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			}
			#pragma unroll_loop_end
			clipOpacity *= 1.0 - unionClipOpacity;
		#endif
		diffuseColor.a *= clipOpacity;
		if ( diffuseColor.a == 0.0 ) discard;
	#else
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			if ( dot( vClipPosition, plane.xyz ) > plane.w ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			bool clipped = true;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				clipped = ( dot( vClipPosition, plane.xyz ) > plane.w ) && clipped;
			}
			#pragma unroll_loop_end
			if ( clipped ) discard;
		#endif
	#endif
#endif`,Bu=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,zu=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,Hu=`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,ku=`#if defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#elif defined( USE_COLOR )
	diffuseColor.rgb *= vColor;
#endif`,Vu=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR )
	varying vec3 vColor;
#endif`,Gu=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec3 vColor;
#endif`,Wu=`#if defined( USE_COLOR_ALPHA )
	vColor = vec4( 1.0 );
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	vColor = vec3( 1.0 );
#endif
#ifdef USE_COLOR
	vColor *= color;
#endif
#ifdef USE_INSTANCING_COLOR
	vColor.xyz *= instanceColor.xyz;
#endif
#ifdef USE_BATCHING_COLOR
	vec3 batchingColor = getBatchingColor( getIndirectIndex( gl_DrawID ) );
	vColor.xyz *= batchingColor.xyz;
#endif`,Xu=`#define PI 3.141592653589793
#define PI2 6.283185307179586
#define PI_HALF 1.5707963267948966
#define RECIPROCAL_PI 0.3183098861837907
#define RECIPROCAL_PI2 0.15915494309189535
#define EPSILON 1e-6
#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
#define whiteComplement( a ) ( 1.0 - saturate( a ) )
float pow2( const in float x ) { return x*x; }
vec3 pow2( const in vec3 x ) { return x*x; }
float pow3( const in float x ) { return x*x*x; }
float pow4( const in float x ) { float x2 = x*x; return x2*x2; }
float max3( const in vec3 v ) { return max( max( v.x, v.y ), v.z ); }
float average( const in vec3 v ) { return dot( v, vec3( 0.3333333 ) ); }
highp float rand( const in vec2 uv ) {
	const highp float a = 12.9898, b = 78.233, c = 43758.5453;
	highp float dt = dot( uv.xy, vec2( a,b ) ), sn = mod( dt, PI );
	return fract( sin( sn ) * c );
}
#ifdef HIGH_PRECISION
	float precisionSafeLength( vec3 v ) { return length( v ); }
#else
	float precisionSafeLength( vec3 v ) {
		float maxComponent = max3( abs( v ) );
		return length( v / maxComponent ) * maxComponent;
	}
#endif
struct IncidentLight {
	vec3 color;
	vec3 direction;
	bool visible;
};
struct ReflectedLight {
	vec3 directDiffuse;
	vec3 directSpecular;
	vec3 indirectDiffuse;
	vec3 indirectSpecular;
};
#ifdef USE_ALPHAHASH
	varying vec3 vPosition;
#endif
vec3 transformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );
}
vec3 inverseTransformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( vec4( dir, 0.0 ) * matrix ).xyz );
}
mat3 transposeMat3( const in mat3 m ) {
	mat3 tmp;
	tmp[ 0 ] = vec3( m[ 0 ].x, m[ 1 ].x, m[ 2 ].x );
	tmp[ 1 ] = vec3( m[ 0 ].y, m[ 1 ].y, m[ 2 ].y );
	tmp[ 2 ] = vec3( m[ 0 ].z, m[ 1 ].z, m[ 2 ].z );
	return tmp;
}
bool isPerspectiveMatrix( mat4 m ) {
	return m[ 2 ][ 3 ] == - 1.0;
}
vec2 equirectUv( in vec3 dir ) {
	float u = atan( dir.z, dir.x ) * RECIPROCAL_PI2 + 0.5;
	float v = asin( clamp( dir.y, - 1.0, 1.0 ) ) * RECIPROCAL_PI + 0.5;
	return vec2( u, v );
}
vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
	return RECIPROCAL_PI * diffuseColor;
}
vec3 F_Schlick( const in vec3 f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
}
float F_Schlick( const in float f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
} // validated`,qu=`#ifdef ENVMAP_TYPE_CUBE_UV
	#define cubeUV_minMipLevel 4.0
	#define cubeUV_minTileSize 16.0
	float getFace( vec3 direction ) {
		vec3 absDirection = abs( direction );
		float face = - 1.0;
		if ( absDirection.x > absDirection.z ) {
			if ( absDirection.x > absDirection.y )
				face = direction.x > 0.0 ? 0.0 : 3.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		} else {
			if ( absDirection.z > absDirection.y )
				face = direction.z > 0.0 ? 2.0 : 5.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		}
		return face;
	}
	vec2 getUV( vec3 direction, float face ) {
		vec2 uv;
		if ( face == 0.0 ) {
			uv = vec2( direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 1.0 ) {
			uv = vec2( - direction.x, - direction.z ) / abs( direction.y );
		} else if ( face == 2.0 ) {
			uv = vec2( - direction.x, direction.y ) / abs( direction.z );
		} else if ( face == 3.0 ) {
			uv = vec2( - direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 4.0 ) {
			uv = vec2( - direction.x, direction.z ) / abs( direction.y );
		} else {
			uv = vec2( direction.x, direction.y ) / abs( direction.z );
		}
		return 0.5 * ( uv + 1.0 );
	}
	vec3 bilinearCubeUV( sampler2D envMap, vec3 direction, float mipInt ) {
		float face = getFace( direction );
		float filterInt = max( cubeUV_minMipLevel - mipInt, 0.0 );
		mipInt = max( mipInt, cubeUV_minMipLevel );
		float faceSize = exp2( mipInt );
		highp vec2 uv = getUV( direction, face ) * ( faceSize - 2.0 ) + 1.0;
		if ( face > 2.0 ) {
			uv.y += faceSize;
			face -= 3.0;
		}
		uv.x += face * faceSize;
		uv.x += filterInt * 3.0 * cubeUV_minTileSize;
		uv.y += 4.0 * ( exp2( CUBEUV_MAX_MIP ) - faceSize );
		uv.x *= CUBEUV_TEXEL_WIDTH;
		uv.y *= CUBEUV_TEXEL_HEIGHT;
		#ifdef texture2DGradEXT
			return texture2DGradEXT( envMap, uv, vec2( 0.0 ), vec2( 0.0 ) ).rgb;
		#else
			return texture2D( envMap, uv ).rgb;
		#endif
	}
	#define cubeUV_r0 1.0
	#define cubeUV_m0 - 2.0
	#define cubeUV_r1 0.8
	#define cubeUV_m1 - 1.0
	#define cubeUV_r4 0.4
	#define cubeUV_m4 2.0
	#define cubeUV_r5 0.305
	#define cubeUV_m5 3.0
	#define cubeUV_r6 0.21
	#define cubeUV_m6 4.0
	float roughnessToMip( float roughness ) {
		float mip = 0.0;
		if ( roughness >= cubeUV_r1 ) {
			mip = ( cubeUV_r0 - roughness ) * ( cubeUV_m1 - cubeUV_m0 ) / ( cubeUV_r0 - cubeUV_r1 ) + cubeUV_m0;
		} else if ( roughness >= cubeUV_r4 ) {
			mip = ( cubeUV_r1 - roughness ) * ( cubeUV_m4 - cubeUV_m1 ) / ( cubeUV_r1 - cubeUV_r4 ) + cubeUV_m1;
		} else if ( roughness >= cubeUV_r5 ) {
			mip = ( cubeUV_r4 - roughness ) * ( cubeUV_m5 - cubeUV_m4 ) / ( cubeUV_r4 - cubeUV_r5 ) + cubeUV_m4;
		} else if ( roughness >= cubeUV_r6 ) {
			mip = ( cubeUV_r5 - roughness ) * ( cubeUV_m6 - cubeUV_m5 ) / ( cubeUV_r5 - cubeUV_r6 ) + cubeUV_m5;
		} else {
			mip = - 2.0 * log2( 1.16 * roughness );		}
		return mip;
	}
	vec4 textureCubeUV( sampler2D envMap, vec3 sampleDir, float roughness ) {
		float mip = clamp( roughnessToMip( roughness ), cubeUV_m0, CUBEUV_MAX_MIP );
		float mipF = fract( mip );
		float mipInt = floor( mip );
		vec3 color0 = bilinearCubeUV( envMap, sampleDir, mipInt );
		if ( mipF == 0.0 ) {
			return vec4( color0, 1.0 );
		} else {
			vec3 color1 = bilinearCubeUV( envMap, sampleDir, mipInt + 1.0 );
			return vec4( mix( color0, color1, mipF ), 1.0 );
		}
	}
#endif`,Yu=`vec3 transformedNormal = objectNormal;
#ifdef USE_TANGENT
	vec3 transformedTangent = objectTangent;
#endif
#ifdef USE_BATCHING
	mat3 bm = mat3( batchingMatrix );
	transformedNormal /= vec3( dot( bm[ 0 ], bm[ 0 ] ), dot( bm[ 1 ], bm[ 1 ] ), dot( bm[ 2 ], bm[ 2 ] ) );
	transformedNormal = bm * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = bm * transformedTangent;
	#endif
#endif
#ifdef USE_INSTANCING
	mat3 im = mat3( instanceMatrix );
	transformedNormal /= vec3( dot( im[ 0 ], im[ 0 ] ), dot( im[ 1 ], im[ 1 ] ), dot( im[ 2 ], im[ 2 ] ) );
	transformedNormal = im * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = im * transformedTangent;
	#endif
#endif
transformedNormal = normalMatrix * transformedNormal;
#ifdef FLIP_SIDED
	transformedNormal = - transformedNormal;
#endif
#ifdef USE_TANGENT
	transformedTangent = ( modelViewMatrix * vec4( transformedTangent, 0.0 ) ).xyz;
	#ifdef FLIP_SIDED
		transformedTangent = - transformedTangent;
	#endif
#endif`,ju=`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,Ku=`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,Zu=`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,$u=`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,Ju="gl_FragColor = linearToOutputTexel( gl_FragColor );",Qu=`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,eh=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vec3 cameraToFrag;
		if ( isOrthographic ) {
			cameraToFrag = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToFrag = normalize( vWorldPosition - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vec3 reflectVec = reflect( cameraToFrag, worldNormal );
		#else
			vec3 reflectVec = refract( cameraToFrag, worldNormal, refractionRatio );
		#endif
	#else
		vec3 reflectVec = vReflect;
	#endif
	#ifdef ENVMAP_TYPE_CUBE
		vec4 envColor = textureCube( envMap, envMapRotation * vec3( flipEnvMap * reflectVec.x, reflectVec.yz ) );
	#else
		vec4 envColor = vec4( 0.0 );
	#endif
	#ifdef ENVMAP_BLENDING_MULTIPLY
		outgoingLight = mix( outgoingLight, outgoingLight * envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_MIX )
		outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_ADD )
		outgoingLight += envColor.xyz * specularStrength * reflectivity;
	#endif
#endif`,th=`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform float flipEnvMap;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
	
#endif`,nh=`#ifdef USE_ENVMAP
	uniform float reflectivity;
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		varying vec3 vWorldPosition;
		uniform float refractionRatio;
	#else
		varying vec3 vReflect;
	#endif
#endif`,ih=`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,rh=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vWorldPosition = worldPosition.xyz;
	#else
		vec3 cameraToVertex;
		if ( isOrthographic ) {
			cameraToVertex = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vReflect = reflect( cameraToVertex, worldNormal );
		#else
			vReflect = refract( cameraToVertex, worldNormal, refractionRatio );
		#endif
	#endif
#endif`,sh=`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,oh=`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,ah=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,lh=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,ch=`#ifdef USE_GRADIENTMAP
	uniform sampler2D gradientMap;
#endif
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
	float dotNL = dot( normal, lightDirection );
	vec2 coord = vec2( dotNL * 0.5 + 0.5, 0.0 );
	#ifdef USE_GRADIENTMAP
		return vec3( texture2D( gradientMap, coord ).r );
	#else
		vec2 fw = fwidth( coord ) * 0.5;
		return mix( vec3( 0.7 ), vec3( 1.0 ), smoothstep( 0.7 - fw.x, 0.7 + fw.x, coord.x ) );
	#endif
}`,uh=`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,hh=`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,dh=`varying vec3 vViewPosition;
struct LambertMaterial {
	vec3 diffuseColor;
	float specularStrength;
};
void RE_Direct_Lambert( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Lambert( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Lambert
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,fh=`uniform bool receiveShadow;
uniform vec3 ambientLightColor;
#if defined( USE_LIGHT_PROBES )
	uniform vec3 lightProbe[ 9 ];
#endif
vec3 shGetIrradianceAt( in vec3 normal, in vec3 shCoefficients[ 9 ] ) {
	float x = normal.x, y = normal.y, z = normal.z;
	vec3 result = shCoefficients[ 0 ] * 0.886227;
	result += shCoefficients[ 1 ] * 2.0 * 0.511664 * y;
	result += shCoefficients[ 2 ] * 2.0 * 0.511664 * z;
	result += shCoefficients[ 3 ] * 2.0 * 0.511664 * x;
	result += shCoefficients[ 4 ] * 2.0 * 0.429043 * x * y;
	result += shCoefficients[ 5 ] * 2.0 * 0.429043 * y * z;
	result += shCoefficients[ 6 ] * ( 0.743125 * z * z - 0.247708 );
	result += shCoefficients[ 7 ] * 2.0 * 0.429043 * x * z;
	result += shCoefficients[ 8 ] * 0.429043 * ( x * x - y * y );
	return result;
}
vec3 getLightProbeIrradiance( const in vec3 lightProbe[ 9 ], const in vec3 normal ) {
	vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
	vec3 irradiance = shGetIrradianceAt( worldNormal, lightProbe );
	return irradiance;
}
vec3 getAmbientLightIrradiance( const in vec3 ambientLightColor ) {
	vec3 irradiance = ambientLightColor;
	return irradiance;
}
float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {
	float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), 0.01 );
	if ( cutoffDistance > 0.0 ) {
		distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );
	}
	return distanceFalloff;
}
float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {
	return smoothstep( coneCosine, penumbraCosine, angleCosine );
}
#if NUM_DIR_LIGHTS > 0
	struct DirectionalLight {
		vec3 direction;
		vec3 color;
	};
	uniform DirectionalLight directionalLights[ NUM_DIR_LIGHTS ];
	void getDirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
		light.color = directionalLight.color;
		light.direction = directionalLight.direction;
		light.visible = true;
	}
#endif
#if NUM_POINT_LIGHTS > 0
	struct PointLight {
		vec3 position;
		vec3 color;
		float distance;
		float decay;
	};
	uniform PointLight pointLights[ NUM_POINT_LIGHTS ];
	void getPointLightInfo( const in PointLight pointLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = pointLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float lightDistance = length( lVector );
		light.color = pointLight.color;
		light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );
		light.visible = ( light.color != vec3( 0.0 ) );
	}
#endif
#if NUM_SPOT_LIGHTS > 0
	struct SpotLight {
		vec3 position;
		vec3 direction;
		vec3 color;
		float distance;
		float decay;
		float coneCos;
		float penumbraCos;
	};
	uniform SpotLight spotLights[ NUM_SPOT_LIGHTS ];
	void getSpotLightInfo( const in SpotLight spotLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = spotLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float angleCos = dot( light.direction, spotLight.direction );
		float spotAttenuation = getSpotAttenuation( spotLight.coneCos, spotLight.penumbraCos, angleCos );
		if ( spotAttenuation > 0.0 ) {
			float lightDistance = length( lVector );
			light.color = spotLight.color * spotAttenuation;
			light.color *= getDistanceAttenuation( lightDistance, spotLight.distance, spotLight.decay );
			light.visible = ( light.color != vec3( 0.0 ) );
		} else {
			light.color = vec3( 0.0 );
			light.visible = false;
		}
	}
#endif
#if NUM_RECT_AREA_LIGHTS > 0
	struct RectAreaLight {
		vec3 color;
		vec3 position;
		vec3 halfWidth;
		vec3 halfHeight;
	};
	uniform sampler2D ltc_1;	uniform sampler2D ltc_2;
	uniform RectAreaLight rectAreaLights[ NUM_RECT_AREA_LIGHTS ];
#endif
#if NUM_HEMI_LIGHTS > 0
	struct HemisphereLight {
		vec3 direction;
		vec3 skyColor;
		vec3 groundColor;
	};
	uniform HemisphereLight hemisphereLights[ NUM_HEMI_LIGHTS ];
	vec3 getHemisphereLightIrradiance( const in HemisphereLight hemiLight, const in vec3 normal ) {
		float dotNL = dot( normal, hemiLight.direction );
		float hemiDiffuseWeight = 0.5 * dotNL + 0.5;
		vec3 irradiance = mix( hemiLight.groundColor, hemiLight.skyColor, hemiDiffuseWeight );
		return irradiance;
	}
#endif`,ph=`#ifdef USE_ENVMAP
	vec3 getIBLIrradiance( const in vec3 normal ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * worldNormal, 1.0 );
			return PI * envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 reflectVec = reflect( - viewDir, normal );
			reflectVec = normalize( mix( reflectVec, normal, roughness * roughness) );
			reflectVec = inverseTransformDirection( reflectVec, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );
			return envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	#ifdef USE_ANISOTROPY
		vec3 getIBLAnisotropyRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 bentNormal = cross( bitangent, viewDir );
				bentNormal = normalize( cross( bentNormal, bitangent ) );
				bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
				return getIBLRadiance( viewDir, bentNormal, roughness );
			#else
				return vec3( 0.0 );
			#endif
		}
	#endif
#endif`,mh=`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,gh=`varying vec3 vViewPosition;
struct ToonMaterial {
	vec3 diffuseColor;
};
void RE_Direct_Toon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 irradiance = getGradientIrradiance( geometryNormal, directLight.direction ) * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Toon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Toon
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,_h=`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,vh=`varying vec3 vViewPosition;
struct BlinnPhongMaterial {
	vec3 diffuseColor;
	vec3 specularColor;
	float specularShininess;
	float specularStrength;
};
void RE_Direct_BlinnPhong( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
	reflectedLight.directSpecular += irradiance * BRDF_BlinnPhong( directLight.direction, geometryViewDir, geometryNormal, material.specularColor, material.specularShininess ) * material.specularStrength;
}
void RE_IndirectDiffuse_BlinnPhong( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_BlinnPhong
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,xh=`PhysicalMaterial material;
material.diffuseColor = diffuseColor.rgb * ( 1.0 - metalnessFactor );
vec3 dxy = max( abs( dFdx( nonPerturbedNormal ) ), abs( dFdy( nonPerturbedNormal ) ) );
float geometryRoughness = max( max( dxy.x, dxy.y ), dxy.z );
material.roughness = max( roughnessFactor, 0.0525 );material.roughness += geometryRoughness;
material.roughness = min( material.roughness, 1.0 );
#ifdef IOR
	material.ior = ior;
	#ifdef USE_SPECULAR
		float specularIntensityFactor = specularIntensity;
		vec3 specularColorFactor = specularColor;
		#ifdef USE_SPECULAR_COLORMAP
			specularColorFactor *= texture2D( specularColorMap, vSpecularColorMapUv ).rgb;
		#endif
		#ifdef USE_SPECULAR_INTENSITYMAP
			specularIntensityFactor *= texture2D( specularIntensityMap, vSpecularIntensityMapUv ).a;
		#endif
		material.specularF90 = mix( specularIntensityFactor, 1.0, metalnessFactor );
	#else
		float specularIntensityFactor = 1.0;
		vec3 specularColorFactor = vec3( 1.0 );
		material.specularF90 = 1.0;
	#endif
	material.specularColor = mix( min( pow2( ( material.ior - 1.0 ) / ( material.ior + 1.0 ) ) * specularColorFactor, vec3( 1.0 ) ) * specularIntensityFactor, diffuseColor.rgb, metalnessFactor );
#else
	material.specularColor = mix( vec3( 0.04 ), diffuseColor.rgb, metalnessFactor );
	material.specularF90 = 1.0;
#endif
#ifdef USE_CLEARCOAT
	material.clearcoat = clearcoat;
	material.clearcoatRoughness = clearcoatRoughness;
	material.clearcoatF0 = vec3( 0.04 );
	material.clearcoatF90 = 1.0;
	#ifdef USE_CLEARCOATMAP
		material.clearcoat *= texture2D( clearcoatMap, vClearcoatMapUv ).x;
	#endif
	#ifdef USE_CLEARCOAT_ROUGHNESSMAP
		material.clearcoatRoughness *= texture2D( clearcoatRoughnessMap, vClearcoatRoughnessMapUv ).y;
	#endif
	material.clearcoat = saturate( material.clearcoat );	material.clearcoatRoughness = max( material.clearcoatRoughness, 0.0525 );
	material.clearcoatRoughness += geometryRoughness;
	material.clearcoatRoughness = min( material.clearcoatRoughness, 1.0 );
#endif
#ifdef USE_DISPERSION
	material.dispersion = dispersion;
#endif
#ifdef USE_IRIDESCENCE
	material.iridescence = iridescence;
	material.iridescenceIOR = iridescenceIOR;
	#ifdef USE_IRIDESCENCEMAP
		material.iridescence *= texture2D( iridescenceMap, vIridescenceMapUv ).r;
	#endif
	#ifdef USE_IRIDESCENCE_THICKNESSMAP
		material.iridescenceThickness = (iridescenceThicknessMaximum - iridescenceThicknessMinimum) * texture2D( iridescenceThicknessMap, vIridescenceThicknessMapUv ).g + iridescenceThicknessMinimum;
	#else
		material.iridescenceThickness = iridescenceThicknessMaximum;
	#endif
#endif
#ifdef USE_SHEEN
	material.sheenColor = sheenColor;
	#ifdef USE_SHEEN_COLORMAP
		material.sheenColor *= texture2D( sheenColorMap, vSheenColorMapUv ).rgb;
	#endif
	material.sheenRoughness = clamp( sheenRoughness, 0.07, 1.0 );
	#ifdef USE_SHEEN_ROUGHNESSMAP
		material.sheenRoughness *= texture2D( sheenRoughnessMap, vSheenRoughnessMapUv ).a;
	#endif
#endif
#ifdef USE_ANISOTROPY
	#ifdef USE_ANISOTROPYMAP
		mat2 anisotropyMat = mat2( anisotropyVector.x, anisotropyVector.y, - anisotropyVector.y, anisotropyVector.x );
		vec3 anisotropyPolar = texture2D( anisotropyMap, vAnisotropyMapUv ).rgb;
		vec2 anisotropyV = anisotropyMat * normalize( 2.0 * anisotropyPolar.rg - vec2( 1.0 ) ) * anisotropyPolar.b;
	#else
		vec2 anisotropyV = anisotropyVector;
	#endif
	material.anisotropy = length( anisotropyV );
	if( material.anisotropy == 0.0 ) {
		anisotropyV = vec2( 1.0, 0.0 );
	} else {
		anisotropyV /= material.anisotropy;
		material.anisotropy = saturate( material.anisotropy );
	}
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	material.anisotropyT = tbn[ 0 ] * anisotropyV.x + tbn[ 1 ] * anisotropyV.y;
	material.anisotropyB = tbn[ 1 ] * anisotropyV.x - tbn[ 0 ] * anisotropyV.y;
#endif`,Mh=`struct PhysicalMaterial {
	vec3 diffuseColor;
	float roughness;
	vec3 specularColor;
	float specularF90;
	float dispersion;
	#ifdef USE_CLEARCOAT
		float clearcoat;
		float clearcoatRoughness;
		vec3 clearcoatF0;
		float clearcoatF90;
	#endif
	#ifdef USE_IRIDESCENCE
		float iridescence;
		float iridescenceIOR;
		float iridescenceThickness;
		vec3 iridescenceFresnel;
		vec3 iridescenceF0;
	#endif
	#ifdef USE_SHEEN
		vec3 sheenColor;
		float sheenRoughness;
	#endif
	#ifdef IOR
		float ior;
	#endif
	#ifdef USE_TRANSMISSION
		float transmission;
		float transmissionAlpha;
		float thickness;
		float attenuationDistance;
		vec3 attenuationColor;
	#endif
	#ifdef USE_ANISOTROPY
		float anisotropy;
		float alphaT;
		vec3 anisotropyT;
		vec3 anisotropyB;
	#endif
};
vec3 clearcoatSpecularDirect = vec3( 0.0 );
vec3 clearcoatSpecularIndirect = vec3( 0.0 );
vec3 sheenSpecularDirect = vec3( 0.0 );
vec3 sheenSpecularIndirect = vec3(0.0 );
vec3 Schlick_to_F0( const in vec3 f, const in float f90, const in float dotVH ) {
    float x = clamp( 1.0 - dotVH, 0.0, 1.0 );
    float x2 = x * x;
    float x5 = clamp( x * x2 * x2, 0.0, 0.9999 );
    return ( f - vec3( f90 ) * x5 ) / ( 1.0 - x5 );
}
float V_GGX_SmithCorrelated( const in float alpha, const in float dotNL, const in float dotNV ) {
	float a2 = pow2( alpha );
	float gv = dotNL * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNV ) );
	float gl = dotNV * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNL ) );
	return 0.5 / max( gv + gl, EPSILON );
}
float D_GGX( const in float alpha, const in float dotNH ) {
	float a2 = pow2( alpha );
	float denom = pow2( dotNH ) * ( a2 - 1.0 ) + 1.0;
	return RECIPROCAL_PI * a2 / pow2( denom );
}
#ifdef USE_ANISOTROPY
	float V_GGX_SmithCorrelated_Anisotropic( const in float alphaT, const in float alphaB, const in float dotTV, const in float dotBV, const in float dotTL, const in float dotBL, const in float dotNV, const in float dotNL ) {
		float gv = dotNL * length( vec3( alphaT * dotTV, alphaB * dotBV, dotNV ) );
		float gl = dotNV * length( vec3( alphaT * dotTL, alphaB * dotBL, dotNL ) );
		float v = 0.5 / ( gv + gl );
		return saturate(v);
	}
	float D_GGX_Anisotropic( const in float alphaT, const in float alphaB, const in float dotNH, const in float dotTH, const in float dotBH ) {
		float a2 = alphaT * alphaB;
		highp vec3 v = vec3( alphaB * dotTH, alphaT * dotBH, a2 * dotNH );
		highp float v2 = dot( v, v );
		float w2 = a2 / v2;
		return RECIPROCAL_PI * a2 * pow2 ( w2 );
	}
#endif
#ifdef USE_CLEARCOAT
	vec3 BRDF_GGX_Clearcoat( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material) {
		vec3 f0 = material.clearcoatF0;
		float f90 = material.clearcoatF90;
		float roughness = material.clearcoatRoughness;
		float alpha = pow2( roughness );
		vec3 halfDir = normalize( lightDir + viewDir );
		float dotNL = saturate( dot( normal, lightDir ) );
		float dotNV = saturate( dot( normal, viewDir ) );
		float dotNH = saturate( dot( normal, halfDir ) );
		float dotVH = saturate( dot( viewDir, halfDir ) );
		vec3 F = F_Schlick( f0, f90, dotVH );
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
		return F * ( V * D );
	}
#endif
vec3 BRDF_GGX( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 f0 = material.specularColor;
	float f90 = material.specularF90;
	float roughness = material.roughness;
	float alpha = pow2( roughness );
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( f0, f90, dotVH );
	#ifdef USE_IRIDESCENCE
		F = mix( F, material.iridescenceFresnel, material.iridescence );
	#endif
	#ifdef USE_ANISOTROPY
		float dotTL = dot( material.anisotropyT, lightDir );
		float dotTV = dot( material.anisotropyT, viewDir );
		float dotTH = dot( material.anisotropyT, halfDir );
		float dotBL = dot( material.anisotropyB, lightDir );
		float dotBV = dot( material.anisotropyB, viewDir );
		float dotBH = dot( material.anisotropyB, halfDir );
		float V = V_GGX_SmithCorrelated_Anisotropic( material.alphaT, alpha, dotTV, dotBV, dotTL, dotBL, dotNV, dotNL );
		float D = D_GGX_Anisotropic( material.alphaT, alpha, dotNH, dotTH, dotBH );
	#else
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
	#endif
	return F * ( V * D );
}
vec2 LTC_Uv( const in vec3 N, const in vec3 V, const in float roughness ) {
	const float LUT_SIZE = 64.0;
	const float LUT_SCALE = ( LUT_SIZE - 1.0 ) / LUT_SIZE;
	const float LUT_BIAS = 0.5 / LUT_SIZE;
	float dotNV = saturate( dot( N, V ) );
	vec2 uv = vec2( roughness, sqrt( 1.0 - dotNV ) );
	uv = uv * LUT_SCALE + LUT_BIAS;
	return uv;
}
float LTC_ClippedSphereFormFactor( const in vec3 f ) {
	float l = length( f );
	return max( ( l * l + f.z ) / ( l + 1.0 ), 0.0 );
}
vec3 LTC_EdgeVectorFormFactor( const in vec3 v1, const in vec3 v2 ) {
	float x = dot( v1, v2 );
	float y = abs( x );
	float a = 0.8543985 + ( 0.4965155 + 0.0145206 * y ) * y;
	float b = 3.4175940 + ( 4.1616724 + y ) * y;
	float v = a / b;
	float theta_sintheta = ( x > 0.0 ) ? v : 0.5 * inversesqrt( max( 1.0 - x * x, 1e-7 ) ) - v;
	return cross( v1, v2 ) * theta_sintheta;
}
vec3 LTC_Evaluate( const in vec3 N, const in vec3 V, const in vec3 P, const in mat3 mInv, const in vec3 rectCoords[ 4 ] ) {
	vec3 v1 = rectCoords[ 1 ] - rectCoords[ 0 ];
	vec3 v2 = rectCoords[ 3 ] - rectCoords[ 0 ];
	vec3 lightNormal = cross( v1, v2 );
	if( dot( lightNormal, P - rectCoords[ 0 ] ) < 0.0 ) return vec3( 0.0 );
	vec3 T1, T2;
	T1 = normalize( V - N * dot( V, N ) );
	T2 = - cross( N, T1 );
	mat3 mat = mInv * transposeMat3( mat3( T1, T2, N ) );
	vec3 coords[ 4 ];
	coords[ 0 ] = mat * ( rectCoords[ 0 ] - P );
	coords[ 1 ] = mat * ( rectCoords[ 1 ] - P );
	coords[ 2 ] = mat * ( rectCoords[ 2 ] - P );
	coords[ 3 ] = mat * ( rectCoords[ 3 ] - P );
	coords[ 0 ] = normalize( coords[ 0 ] );
	coords[ 1 ] = normalize( coords[ 1 ] );
	coords[ 2 ] = normalize( coords[ 2 ] );
	coords[ 3 ] = normalize( coords[ 3 ] );
	vec3 vectorFormFactor = vec3( 0.0 );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 0 ], coords[ 1 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 1 ], coords[ 2 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 2 ], coords[ 3 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 3 ], coords[ 0 ] );
	float result = LTC_ClippedSphereFormFactor( vectorFormFactor );
	return vec3( result );
}
#if defined( USE_SHEEN )
float D_Charlie( float roughness, float dotNH ) {
	float alpha = pow2( roughness );
	float invAlpha = 1.0 / alpha;
	float cos2h = dotNH * dotNH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );
}
float V_Neubelt( float dotNV, float dotNL ) {
	return saturate( 1.0 / ( 4.0 * ( dotNL + dotNV - dotNL * dotNV ) ) );
}
vec3 BRDF_Sheen( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, vec3 sheenColor, const in float sheenRoughness ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float D = D_Charlie( sheenRoughness, dotNH );
	float V = V_Neubelt( dotNV, dotNL );
	return sheenColor * ( D * V );
}
#endif
float IBLSheenBRDF( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	float r2 = roughness * roughness;
	float a = roughness < 0.25 ? -339.2 * r2 + 161.4 * roughness - 25.9 : -8.48 * r2 + 14.3 * roughness - 9.95;
	float b = roughness < 0.25 ? 44.0 * r2 - 23.7 * roughness + 3.26 : 1.97 * r2 - 3.27 * roughness + 0.72;
	float DG = exp( a * dotNV + b ) + ( roughness < 0.25 ? 0.0 : 0.1 * ( roughness - 0.25 ) );
	return saturate( DG * RECIPROCAL_PI );
}
vec2 DFGApprox( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	const vec4 c0 = vec4( - 1, - 0.0275, - 0.572, 0.022 );
	const vec4 c1 = vec4( 1, 0.0425, 1.04, - 0.04 );
	vec4 r = roughness * c0 + c1;
	float a004 = min( r.x * r.x, exp2( - 9.28 * dotNV ) ) * r.x + r.y;
	vec2 fab = vec2( - 1.04, 1.04 ) * a004 + r.zw;
	return fab;
}
vec3 EnvironmentBRDF( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness ) {
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	return specularColor * fab.x + specularF90 * fab.y;
}
#ifdef USE_IRIDESCENCE
void computeMultiscatteringIridescence( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float iridescence, const in vec3 iridescenceF0, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#else
void computeMultiscattering( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#endif
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	#ifdef USE_IRIDESCENCE
		vec3 Fr = mix( specularColor, iridescenceF0, iridescence );
	#else
		vec3 Fr = specularColor;
	#endif
	vec3 FssEss = Fr * fab.x + specularF90 * fab.y;
	float Ess = fab.x + fab.y;
	float Ems = 1.0 - Ess;
	vec3 Favg = Fr + ( 1.0 - Fr ) * 0.047619;	vec3 Fms = FssEss * Favg / ( 1.0 - Ems * Favg );
	singleScatter += FssEss;
	multiScatter += Fms * Ems;
}
#if NUM_RECT_AREA_LIGHTS > 0
	void RE_Direct_RectArea_Physical( const in RectAreaLight rectAreaLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
		vec3 normal = geometryNormal;
		vec3 viewDir = geometryViewDir;
		vec3 position = geometryPosition;
		vec3 lightPos = rectAreaLight.position;
		vec3 halfWidth = rectAreaLight.halfWidth;
		vec3 halfHeight = rectAreaLight.halfHeight;
		vec3 lightColor = rectAreaLight.color;
		float roughness = material.roughness;
		vec3 rectCoords[ 4 ];
		rectCoords[ 0 ] = lightPos + halfWidth - halfHeight;		rectCoords[ 1 ] = lightPos - halfWidth - halfHeight;
		rectCoords[ 2 ] = lightPos - halfWidth + halfHeight;
		rectCoords[ 3 ] = lightPos + halfWidth + halfHeight;
		vec2 uv = LTC_Uv( normal, viewDir, roughness );
		vec4 t1 = texture2D( ltc_1, uv );
		vec4 t2 = texture2D( ltc_2, uv );
		mat3 mInv = mat3(
			vec3( t1.x, 0, t1.y ),
			vec3(    0, 1,    0 ),
			vec3( t1.z, 0, t1.w )
		);
		vec3 fresnel = ( material.specularColor * t2.x + ( vec3( 1.0 ) - material.specularColor ) * t2.y );
		reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );
		reflectedLight.directDiffuse += lightColor * material.diffuseColor * LTC_Evaluate( normal, viewDir, position, mat3( 1.0 ), rectCoords );
	}
#endif
void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	#ifdef USE_CLEARCOAT
		float dotNLcc = saturate( dot( geometryClearcoatNormal, directLight.direction ) );
		vec3 ccIrradiance = dotNLcc * directLight.color;
		clearcoatSpecularDirect += ccIrradiance * BRDF_GGX_Clearcoat( directLight.direction, geometryViewDir, geometryClearcoatNormal, material );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularDirect += irradiance * BRDF_Sheen( directLight.direction, geometryViewDir, geometryNormal, material.sheenColor, material.sheenRoughness );
	#endif
	reflectedLight.directSpecular += irradiance * BRDF_GGX( directLight.direction, geometryViewDir, geometryNormal, material );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Physical( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectSpecular_Physical( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight) {
	#ifdef USE_CLEARCOAT
		clearcoatSpecularIndirect += clearcoatRadiance * EnvironmentBRDF( geometryClearcoatNormal, geometryViewDir, material.clearcoatF0, material.clearcoatF90, material.clearcoatRoughness );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularIndirect += irradiance * material.sheenColor * IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
	#endif
	vec3 singleScattering = vec3( 0.0 );
	vec3 multiScattering = vec3( 0.0 );
	vec3 cosineWeightedIrradiance = irradiance * RECIPROCAL_PI;
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.iridescence, material.iridescenceFresnel, material.roughness, singleScattering, multiScattering );
	#else
		computeMultiscattering( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.roughness, singleScattering, multiScattering );
	#endif
	vec3 totalScattering = singleScattering + multiScattering;
	vec3 diffuse = material.diffuseColor * ( 1.0 - max( max( totalScattering.r, totalScattering.g ), totalScattering.b ) );
	reflectedLight.indirectSpecular += radiance * singleScattering;
	reflectedLight.indirectSpecular += multiScattering * cosineWeightedIrradiance;
	reflectedLight.indirectDiffuse += diffuse * cosineWeightedIrradiance;
}
#define RE_Direct				RE_Direct_Physical
#define RE_Direct_RectArea		RE_Direct_RectArea_Physical
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Physical
#define RE_IndirectSpecular		RE_IndirectSpecular_Physical
float computeSpecularOcclusion( const in float dotNV, const in float ambientOcclusion, const in float roughness ) {
	return saturate( pow( dotNV + ambientOcclusion, exp2( - 16.0 * roughness - 1.0 ) ) - 1.0 + ambientOcclusion );
}`,Sh=`
vec3 geometryPosition = - vViewPosition;
vec3 geometryNormal = normal;
vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );
vec3 geometryClearcoatNormal = vec3( 0.0 );
#ifdef USE_CLEARCOAT
	geometryClearcoatNormal = clearcoatNormal;
#endif
#ifdef USE_IRIDESCENCE
	float dotNVi = saturate( dot( normal, geometryViewDir ) );
	if ( material.iridescenceThickness == 0.0 ) {
		material.iridescence = 0.0;
	} else {
		material.iridescence = saturate( material.iridescence );
	}
	if ( material.iridescence > 0.0 ) {
		material.iridescenceFresnel = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.specularColor );
		material.iridescenceF0 = Schlick_to_F0( material.iridescenceFresnel, 1.0, dotNVi );
	}
#endif
IncidentLight directLight;
#if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )
	PointLight pointLight;
	#if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {
		pointLight = pointLights[ i ];
		getPointLightInfo( pointLight, geometryPosition, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS )
		pointLightShadow = pointLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )
	SpotLight spotLight;
	vec4 spotColor;
	vec3 spotLightCoord;
	bool inSpotLightMap;
	#if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {
		spotLight = spotLights[ i ];
		getSpotLightInfo( spotLight, geometryPosition, directLight );
		#if ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#define SPOT_LIGHT_MAP_INDEX UNROLLED_LOOP_INDEX
		#elif ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		#define SPOT_LIGHT_MAP_INDEX NUM_SPOT_LIGHT_MAPS
		#else
		#define SPOT_LIGHT_MAP_INDEX ( UNROLLED_LOOP_INDEX - NUM_SPOT_LIGHT_SHADOWS + NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#endif
		#if ( SPOT_LIGHT_MAP_INDEX < NUM_SPOT_LIGHT_MAPS )
			spotLightCoord = vSpotLightCoord[ i ].xyz / vSpotLightCoord[ i ].w;
			inSpotLightMap = all( lessThan( abs( spotLightCoord * 2. - 1. ), vec3( 1.0 ) ) );
			spotColor = texture2D( spotLightMap[ SPOT_LIGHT_MAP_INDEX ], spotLightCoord.xy );
			directLight.color = inSpotLightMap ? directLight.color * spotColor.rgb : directLight.color;
		#endif
		#undef SPOT_LIGHT_MAP_INDEX
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		spotLightShadow = spotLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )
	DirectionalLight directionalLight;
	#if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
		directionalLight = directionalLights[ i ];
		getDirectionalLightInfo( directionalLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
		directionalLightShadow = directionalLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )
	RectAreaLight rectAreaLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {
		rectAreaLight = rectAreaLights[ i ];
		RE_Direct_RectArea( rectAreaLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if defined( RE_IndirectDiffuse )
	vec3 iblIrradiance = vec3( 0.0 );
	vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );
	#if defined( USE_LIGHT_PROBES )
		irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
	#endif
	#if ( NUM_HEMI_LIGHTS > 0 )
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
			irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
		}
		#pragma unroll_loop_end
	#endif
#endif
#if defined( RE_IndirectSpecular )
	vec3 radiance = vec3( 0.0 );
	vec3 clearcoatRadiance = vec3( 0.0 );
#endif`,yh=`#if defined( RE_IndirectDiffuse )
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;
		irradiance += lightMapIrradiance;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD ) && defined( ENVMAP_TYPE_CUBE_UV )
		iblIrradiance += getIBLIrradiance( geometryNormal );
	#endif
#endif
#if defined( USE_ENVMAP ) && defined( RE_IndirectSpecular )
	#ifdef USE_ANISOTROPY
		radiance += getIBLAnisotropyRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
	#else
		radiance += getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );
	#endif
	#ifdef USE_CLEARCOAT
		clearcoatRadiance += getIBLRadiance( geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness );
	#endif
#endif`,Eh=`#if defined( RE_IndirectDiffuse )
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,Th=`#if defined( USE_LOGDEPTHBUF )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,bh=`#if defined( USE_LOGDEPTHBUF )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Ah=`#ifdef USE_LOGDEPTHBUF
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,wh=`#ifdef USE_LOGDEPTHBUF
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,Rh=`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,Ch=`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,Ph=`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
	#if defined( USE_POINTS_UV )
		vec2 uv = vUv;
	#else
		vec2 uv = ( uvTransform * vec3( gl_PointCoord.x, 1.0 - gl_PointCoord.y, 1 ) ).xy;
	#endif
#endif
#ifdef USE_MAP
	diffuseColor *= texture2D( map, uv );
#endif
#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, uv ).g;
#endif`,Dh=`#if defined( USE_POINTS_UV )
	varying vec2 vUv;
#else
	#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
		uniform mat3 uvTransform;
	#endif
#endif
#ifdef USE_MAP
	uniform sampler2D map;
#endif
#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Lh=`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,Uh=`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,Ih=`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,Nh=`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,Fh=`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,Oh=`#ifdef USE_MORPHTARGETS
	#ifndef USE_INSTANCING_MORPH
		uniform float morphTargetBaseInfluence;
		uniform float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	#endif
	uniform sampler2DArray morphTargetsTexture;
	uniform ivec2 morphTargetsTextureSize;
	vec4 getMorph( const in int vertexIndex, const in int morphTargetIndex, const in int offset ) {
		int texelIndex = vertexIndex * MORPHTARGETS_TEXTURE_STRIDE + offset;
		int y = texelIndex / morphTargetsTextureSize.x;
		int x = texelIndex - y * morphTargetsTextureSize.x;
		ivec3 morphUV = ivec3( x, y, morphTargetIndex );
		return texelFetch( morphTargetsTexture, morphUV, 0 );
	}
#endif`,Bh=`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,zh=`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
#ifdef FLAT_SHADED
	vec3 fdx = dFdx( vViewPosition );
	vec3 fdy = dFdy( vViewPosition );
	vec3 normal = normalize( cross( fdx, fdy ) );
#else
	vec3 normal = normalize( vNormal );
	#ifdef DOUBLE_SIDED
		normal *= faceDirection;
	#endif
#endif
#if defined( USE_NORMALMAP_TANGENTSPACE ) || defined( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY )
	#ifdef USE_TANGENT
		mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn = getTangentFrame( - vViewPosition, normal,
		#if defined( USE_NORMALMAP )
			vNormalMapUv
		#elif defined( USE_CLEARCOAT_NORMALMAP )
			vClearcoatNormalMapUv
		#else
			vUv
		#endif
		);
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn[0] *= faceDirection;
		tbn[1] *= faceDirection;
	#endif
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	#ifdef USE_TANGENT
		mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn2[0] *= faceDirection;
		tbn2[1] *= faceDirection;
	#endif
#endif
vec3 nonPerturbedNormal = normal;`,Hh=`#ifdef USE_NORMALMAP_OBJECTSPACE
	normal = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#ifdef FLIP_SIDED
		normal = - normal;
	#endif
	#ifdef DOUBLE_SIDED
		normal = normal * faceDirection;
	#endif
	normal = normalize( normalMatrix * normal );
#elif defined( USE_NORMALMAP_TANGENTSPACE )
	vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	mapN.xy *= normalScale;
	normal = normalize( tbn * mapN );
#elif defined( USE_BUMPMAP )
	normal = perturbNormalArb( - vViewPosition, normal, dHdxy_fwd(), faceDirection );
#endif`,kh=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Vh=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Gh=`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
	#endif
#endif`,Wh=`#ifdef USE_NORMALMAP
	uniform sampler2D normalMap;
	uniform vec2 normalScale;
#endif
#ifdef USE_NORMALMAP_OBJECTSPACE
	uniform mat3 normalMatrix;
#endif
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY ) )
	mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {
		vec3 q0 = dFdx( eye_pos.xyz );
		vec3 q1 = dFdy( eye_pos.xyz );
		vec2 st0 = dFdx( uv.st );
		vec2 st1 = dFdy( uv.st );
		vec3 N = surf_norm;
		vec3 q1perp = cross( q1, N );
		vec3 q0perp = cross( N, q0 );
		vec3 T = q1perp * st0.x + q0perp * st1.x;
		vec3 B = q1perp * st0.y + q0perp * st1.y;
		float det = max( dot( T, T ), dot( B, B ) );
		float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );
		return mat3( T * scale, B * scale, N );
	}
#endif`,Xh=`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,qh=`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,Yh=`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,jh=`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,Kh=`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,Zh=`vec3 packNormalToRGB( const in vec3 normal ) {
	return normalize( normal ) * 0.5 + 0.5;
}
vec3 unpackRGBToNormal( const in vec3 rgb ) {
	return 2.0 * rgb.xyz - 1.0;
}
const float PackUpscale = 256. / 255.;const float UnpackDownscale = 255. / 256.;const float ShiftRight8 = 1. / 256.;
const float Inv255 = 1. / 255.;
const vec4 PackFactors = vec4( 1.0, 256.0, 256.0 * 256.0, 256.0 * 256.0 * 256.0 );
const vec2 UnpackFactors2 = vec2( UnpackDownscale, 1.0 / PackFactors.g );
const vec3 UnpackFactors3 = vec3( UnpackDownscale / PackFactors.rg, 1.0 / PackFactors.b );
const vec4 UnpackFactors4 = vec4( UnpackDownscale / PackFactors.rgb, 1.0 / PackFactors.a );
vec4 packDepthToRGBA( const in float v ) {
	if( v <= 0.0 )
		return vec4( 0., 0., 0., 0. );
	if( v >= 1.0 )
		return vec4( 1., 1., 1., 1. );
	float vuf;
	float af = modf( v * PackFactors.a, vuf );
	float bf = modf( vuf * ShiftRight8, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec4( vuf * Inv255, gf * PackUpscale, bf * PackUpscale, af );
}
vec3 packDepthToRGB( const in float v ) {
	if( v <= 0.0 )
		return vec3( 0., 0., 0. );
	if( v >= 1.0 )
		return vec3( 1., 1., 1. );
	float vuf;
	float bf = modf( v * PackFactors.b, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec3( vuf * Inv255, gf * PackUpscale, bf );
}
vec2 packDepthToRG( const in float v ) {
	if( v <= 0.0 )
		return vec2( 0., 0. );
	if( v >= 1.0 )
		return vec2( 1., 1. );
	float vuf;
	float gf = modf( v * 256., vuf );
	return vec2( vuf * Inv255, gf );
}
float unpackRGBAToDepth( const in vec4 v ) {
	return dot( v, UnpackFactors4 );
}
float unpackRGBToDepth( const in vec3 v ) {
	return dot( v, UnpackFactors3 );
}
float unpackRGToDepth( const in vec2 v ) {
	return v.r * UnpackFactors2.r + v.g * UnpackFactors2.g;
}
vec4 pack2HalfToRGBA( const in vec2 v ) {
	vec4 r = vec4( v.x, fract( v.x * 255.0 ), v.y, fract( v.y * 255.0 ) );
	return vec4( r.x - r.y / 255.0, r.y, r.z - r.w / 255.0, r.w );
}
vec2 unpackRGBATo2Half( const in vec4 v ) {
	return vec2( v.x + ( v.y / 255.0 ), v.z + ( v.w / 255.0 ) );
}
float viewZToOrthographicDepth( const in float viewZ, const in float near, const in float far ) {
	return ( viewZ + near ) / ( near - far );
}
float orthographicDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return depth * ( near - far ) - near;
}
float viewZToPerspectiveDepth( const in float viewZ, const in float near, const in float far ) {
	return ( ( near + viewZ ) * far ) / ( ( far - near ) * viewZ );
}
float perspectiveDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return ( near * far ) / ( ( far - near ) * depth - far );
}`,$h=`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,Jh=`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,Qh=`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,ed=`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,td=`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,nd=`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,id=`#if NUM_SPOT_LIGHT_COORDS > 0
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#if NUM_SPOT_LIGHT_MAPS > 0
	uniform sampler2D spotLightMap[ NUM_SPOT_LIGHT_MAPS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform sampler2D directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		uniform sampler2D spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform sampler2D pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
	float texture2DCompare( sampler2D depths, vec2 uv, float compare ) {
		float depth = unpackRGBAToDepth( texture2D( depths, uv ) );
		#ifdef USE_REVERSEDEPTHBUF
			return step( depth, compare );
		#else
			return step( compare, depth );
		#endif
	}
	vec2 texture2DDistribution( sampler2D shadow, vec2 uv ) {
		return unpackRGBATo2Half( texture2D( shadow, uv ) );
	}
	float VSMShadow (sampler2D shadow, vec2 uv, float compare ){
		float occlusion = 1.0;
		vec2 distribution = texture2DDistribution( shadow, uv );
		#ifdef USE_REVERSEDEPTHBUF
			float hard_shadow = step( distribution.x, compare );
		#else
			float hard_shadow = step( compare , distribution.x );
		#endif
		if (hard_shadow != 1.0 ) {
			float distance = compare - distribution.x ;
			float variance = max( 0.00000, distribution.y * distribution.y );
			float softness_probability = variance / (variance + distance * distance );			softness_probability = clamp( ( softness_probability - 0.3 ) / ( 0.95 - 0.3 ), 0.0, 1.0 );			occlusion = clamp( max( hard_shadow, softness_probability ), 0.0, 1.0 );
		}
		return occlusion;
	}
	float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
		float shadow = 1.0;
		shadowCoord.xyz /= shadowCoord.w;
		shadowCoord.z += shadowBias;
		bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
		bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
		if ( frustumTest ) {
		#if defined( SHADOWMAP_TYPE_PCF )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx0 = - texelSize.x * shadowRadius;
			float dy0 = - texelSize.y * shadowRadius;
			float dx1 = + texelSize.x * shadowRadius;
			float dy1 = + texelSize.y * shadowRadius;
			float dx2 = dx0 / 2.0;
			float dy2 = dy0 / 2.0;
			float dx3 = dx1 / 2.0;
			float dy3 = dy1 / 2.0;
			shadow = (
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy1 ), shadowCoord.z )
			) * ( 1.0 / 17.0 );
		#elif defined( SHADOWMAP_TYPE_PCF_SOFT )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx = texelSize.x;
			float dy = texelSize.y;
			vec2 uv = shadowCoord.xy;
			vec2 f = fract( uv * shadowMapSize + 0.5 );
			uv -= f * texelSize;
			shadow = (
				texture2DCompare( shadowMap, uv, shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( dx, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( 0.0, dy ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + texelSize, shadowCoord.z ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, 0.0 ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 0.0 ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, dy ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( 0.0, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 0.0, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( texture2DCompare( shadowMap, uv + vec2( dx, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( dx, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( mix( texture2DCompare( shadowMap, uv + vec2( -dx, -dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, -dy ), shadowCoord.z ),
						  f.x ),
					 mix( texture2DCompare( shadowMap, uv + vec2( -dx, 2.0 * dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 2.0 * dy ), shadowCoord.z ),
						  f.x ),
					 f.y )
			) * ( 1.0 / 9.0 );
		#elif defined( SHADOWMAP_TYPE_VSM )
			shadow = VSMShadow( shadowMap, shadowCoord.xy, shadowCoord.z );
		#else
			shadow = texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z );
		#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	vec2 cubeToUV( vec3 v, float texelSizeY ) {
		vec3 absV = abs( v );
		float scaleToCube = 1.0 / max( absV.x, max( absV.y, absV.z ) );
		absV *= scaleToCube;
		v *= scaleToCube * ( 1.0 - 2.0 * texelSizeY );
		vec2 planar = v.xy;
		float almostATexel = 1.5 * texelSizeY;
		float almostOne = 1.0 - almostATexel;
		if ( absV.z >= almostOne ) {
			if ( v.z > 0.0 )
				planar.x = 4.0 - v.x;
		} else if ( absV.x >= almostOne ) {
			float signX = sign( v.x );
			planar.x = v.z * signX + 2.0 * signX;
		} else if ( absV.y >= almostOne ) {
			float signY = sign( v.y );
			planar.x = v.x + 2.0 * signY + 2.0;
			planar.y = v.z * signY - 2.0;
		}
		return vec2( 0.125, 0.25 ) * planar + vec2( 0.375, 0.75 );
	}
	float getPointShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		
		float lightToPositionLength = length( lightToPosition );
		if ( lightToPositionLength - shadowCameraFar <= 0.0 && lightToPositionLength - shadowCameraNear >= 0.0 ) {
			float dp = ( lightToPositionLength - shadowCameraNear ) / ( shadowCameraFar - shadowCameraNear );			dp += shadowBias;
			vec3 bd3D = normalize( lightToPosition );
			vec2 texelSize = vec2( 1.0 ) / ( shadowMapSize * vec2( 4.0, 2.0 ) );
			#if defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_PCF_SOFT ) || defined( SHADOWMAP_TYPE_VSM )
				vec2 offset = vec2( - 1, 1 ) * shadowRadius * texelSize.y;
				shadow = (
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxx, texelSize.y ), dp )
				) * ( 1.0 / 9.0 );
			#else
				shadow = texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp );
			#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
#endif`,rd=`#if NUM_SPOT_LIGHT_COORDS > 0
	uniform mat4 spotLightMatrix[ NUM_SPOT_LIGHT_COORDS ];
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform mat4 directionalShadowMatrix[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform mat4 pointShadowMatrix[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
#endif`,sd=`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
	vec3 shadowWorldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
	vec4 shadowWorldPosition;
#endif
#if defined( USE_SHADOWMAP )
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * directionalLightShadows[ i ].shadowNormalBias, 0 );
			vDirectionalShadowCoord[ i ] = directionalShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * pointLightShadows[ i ].shadowNormalBias, 0 );
			vPointShadowCoord[ i ] = pointShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
#endif
#if NUM_SPOT_LIGHT_COORDS > 0
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_COORDS; i ++ ) {
		shadowWorldPosition = worldPosition;
		#if ( defined( USE_SHADOWMAP ) && UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
			shadowWorldPosition.xyz += shadowWorldNormal * spotLightShadows[ i ].shadowNormalBias;
		#endif
		vSpotLightCoord[ i ] = spotLightMatrix[ i ] * shadowWorldPosition;
	}
	#pragma unroll_loop_end
#endif`,od=`float getShadowMask() {
	float shadow = 1.0;
	#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
		directionalLight = directionalLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( directionalShadowMap[ i ], directionalLight.shadowMapSize, directionalLight.shadowIntensity, directionalLight.shadowBias, directionalLight.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_SHADOWS; i ++ ) {
		spotLight = spotLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( spotShadowMap[ i ], spotLight.shadowMapSize, spotLight.shadowIntensity, spotLight.shadowBias, spotLight.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
		pointLight = pointLightShadows[ i ];
		shadow *= receiveShadow ? getPointShadow( pointShadowMap[ i ], pointLight.shadowMapSize, pointLight.shadowIntensity, pointLight.shadowBias, pointLight.shadowRadius, vPointShadowCoord[ i ], pointLight.shadowCameraNear, pointLight.shadowCameraFar ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#endif
	return shadow;
}`,ad=`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,ld=`#ifdef USE_SKINNING
	uniform mat4 bindMatrix;
	uniform mat4 bindMatrixInverse;
	uniform highp sampler2D boneTexture;
	mat4 getBoneMatrix( const in float i ) {
		int size = textureSize( boneTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( boneTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( boneTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( boneTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( boneTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
#endif`,cd=`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,ud=`#ifdef USE_SKINNING
	mat4 skinMatrix = mat4( 0.0 );
	skinMatrix += skinWeight.x * boneMatX;
	skinMatrix += skinWeight.y * boneMatY;
	skinMatrix += skinWeight.z * boneMatZ;
	skinMatrix += skinWeight.w * boneMatW;
	skinMatrix = bindMatrixInverse * skinMatrix * bindMatrix;
	objectNormal = vec4( skinMatrix * vec4( objectNormal, 0.0 ) ).xyz;
	#ifdef USE_TANGENT
		objectTangent = vec4( skinMatrix * vec4( objectTangent, 0.0 ) ).xyz;
	#endif
#endif`,hd=`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,dd=`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,fd=`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,pd=`#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
uniform float toneMappingExposure;
vec3 LinearToneMapping( vec3 color ) {
	return saturate( toneMappingExposure * color );
}
vec3 ReinhardToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	return saturate( color / ( vec3( 1.0 ) + color ) );
}
vec3 CineonToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	color = max( vec3( 0.0 ), color - 0.004 );
	return pow( ( color * ( 6.2 * color + 0.5 ) ) / ( color * ( 6.2 * color + 1.7 ) + 0.06 ), vec3( 2.2 ) );
}
vec3 RRTAndODTFit( vec3 v ) {
	vec3 a = v * ( v + 0.0245786 ) - 0.000090537;
	vec3 b = v * ( 0.983729 * v + 0.4329510 ) + 0.238081;
	return a / b;
}
vec3 ACESFilmicToneMapping( vec3 color ) {
	const mat3 ACESInputMat = mat3(
		vec3( 0.59719, 0.07600, 0.02840 ),		vec3( 0.35458, 0.90834, 0.13383 ),
		vec3( 0.04823, 0.01566, 0.83777 )
	);
	const mat3 ACESOutputMat = mat3(
		vec3(  1.60475, -0.10208, -0.00327 ),		vec3( -0.53108,  1.10813, -0.07276 ),
		vec3( -0.07367, -0.00605,  1.07602 )
	);
	color *= toneMappingExposure / 0.6;
	color = ACESInputMat * color;
	color = RRTAndODTFit( color );
	color = ACESOutputMat * color;
	return saturate( color );
}
const mat3 LINEAR_REC2020_TO_LINEAR_SRGB = mat3(
	vec3( 1.6605, - 0.1246, - 0.0182 ),
	vec3( - 0.5876, 1.1329, - 0.1006 ),
	vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 LINEAR_SRGB_TO_LINEAR_REC2020 = mat3(
	vec3( 0.6274, 0.0691, 0.0164 ),
	vec3( 0.3293, 0.9195, 0.0880 ),
	vec3( 0.0433, 0.0113, 0.8956 )
);
vec3 agxDefaultContrastApprox( vec3 x ) {
	vec3 x2 = x * x;
	vec3 x4 = x2 * x2;
	return + 15.5 * x4 * x2
		- 40.14 * x4 * x
		+ 31.96 * x4
		- 6.868 * x2 * x
		+ 0.4298 * x2
		+ 0.1191 * x
		- 0.00232;
}
vec3 AgXToneMapping( vec3 color ) {
	const mat3 AgXInsetMatrix = mat3(
		vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
		vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
		vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
	);
	const mat3 AgXOutsetMatrix = mat3(
		vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
		vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
		vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
	);
	const float AgxMinEv = - 12.47393;	const float AgxMaxEv = 4.026069;
	color *= toneMappingExposure;
	color = LINEAR_SRGB_TO_LINEAR_REC2020 * color;
	color = AgXInsetMatrix * color;
	color = max( color, 1e-10 );	color = log2( color );
	color = ( color - AgxMinEv ) / ( AgxMaxEv - AgxMinEv );
	color = clamp( color, 0.0, 1.0 );
	color = agxDefaultContrastApprox( color );
	color = AgXOutsetMatrix * color;
	color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
	color = LINEAR_REC2020_TO_LINEAR_SRGB * color;
	color = clamp( color, 0.0, 1.0 );
	return color;
}
vec3 NeutralToneMapping( vec3 color ) {
	const float StartCompression = 0.8 - 0.04;
	const float Desaturation = 0.15;
	color *= toneMappingExposure;
	float x = min( color.r, min( color.g, color.b ) );
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max( color.r, max( color.g, color.b ) );
	if ( peak < StartCompression ) return color;
	float d = 1. - StartCompression;
	float newPeak = 1. - d * d / ( peak + d - StartCompression );
	color *= newPeak / peak;
	float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
	return mix( color, vec3( newPeak ), g );
}
vec3 CustomToneMapping( vec3 color ) { return color; }`,md=`#ifdef USE_TRANSMISSION
	material.transmission = transmission;
	material.transmissionAlpha = 1.0;
	material.thickness = thickness;
	material.attenuationDistance = attenuationDistance;
	material.attenuationColor = attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		material.transmission *= texture2D( transmissionMap, vTransmissionMapUv ).r;
	#endif
	#ifdef USE_THICKNESSMAP
		material.thickness *= texture2D( thicknessMap, vThicknessMapUv ).g;
	#endif
	vec3 pos = vWorldPosition;
	vec3 v = normalize( cameraPosition - pos );
	vec3 n = inverseTransformDirection( normal, viewMatrix );
	vec4 transmitted = getIBLVolumeRefraction(
		n, v, material.roughness, material.diffuseColor, material.specularColor, material.specularF90,
		pos, modelMatrix, viewMatrix, projectionMatrix, material.dispersion, material.ior, material.thickness,
		material.attenuationColor, material.attenuationDistance );
	material.transmissionAlpha = mix( material.transmissionAlpha, transmitted.a, material.transmission );
	totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );
#endif`,gd=`#ifdef USE_TRANSMISSION
	uniform float transmission;
	uniform float thickness;
	uniform float attenuationDistance;
	uniform vec3 attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		uniform sampler2D transmissionMap;
	#endif
	#ifdef USE_THICKNESSMAP
		uniform sampler2D thicknessMap;
	#endif
	uniform vec2 transmissionSamplerSize;
	uniform sampler2D transmissionSamplerMap;
	uniform mat4 modelMatrix;
	uniform mat4 projectionMatrix;
	varying vec3 vWorldPosition;
	float w0( float a ) {
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - a + 3.0 ) - 3.0 ) + 1.0 );
	}
	float w1( float a ) {
		return ( 1.0 / 6.0 ) * ( a *  a * ( 3.0 * a - 6.0 ) + 4.0 );
	}
	float w2( float a ){
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - 3.0 * a + 3.0 ) + 3.0 ) + 1.0 );
	}
	float w3( float a ) {
		return ( 1.0 / 6.0 ) * ( a * a * a );
	}
	float g0( float a ) {
		return w0( a ) + w1( a );
	}
	float g1( float a ) {
		return w2( a ) + w3( a );
	}
	float h0( float a ) {
		return - 1.0 + w1( a ) / ( w0( a ) + w1( a ) );
	}
	float h1( float a ) {
		return 1.0 + w3( a ) / ( w2( a ) + w3( a ) );
	}
	vec4 bicubic( sampler2D tex, vec2 uv, vec4 texelSize, float lod ) {
		uv = uv * texelSize.zw + 0.5;
		vec2 iuv = floor( uv );
		vec2 fuv = fract( uv );
		float g0x = g0( fuv.x );
		float g1x = g1( fuv.x );
		float h0x = h0( fuv.x );
		float h1x = h1( fuv.x );
		float h0y = h0( fuv.y );
		float h1y = h1( fuv.y );
		vec2 p0 = ( vec2( iuv.x + h0x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p1 = ( vec2( iuv.x + h1x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p2 = ( vec2( iuv.x + h0x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		vec2 p3 = ( vec2( iuv.x + h1x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		return g0( fuv.y ) * ( g0x * textureLod( tex, p0, lod ) + g1x * textureLod( tex, p1, lod ) ) +
			g1( fuv.y ) * ( g0x * textureLod( tex, p2, lod ) + g1x * textureLod( tex, p3, lod ) );
	}
	vec4 textureBicubic( sampler2D sampler, vec2 uv, float lod ) {
		vec2 fLodSize = vec2( textureSize( sampler, int( lod ) ) );
		vec2 cLodSize = vec2( textureSize( sampler, int( lod + 1.0 ) ) );
		vec2 fLodSizeInv = 1.0 / fLodSize;
		vec2 cLodSizeInv = 1.0 / cLodSize;
		vec4 fSample = bicubic( sampler, uv, vec4( fLodSizeInv, fLodSize ), floor( lod ) );
		vec4 cSample = bicubic( sampler, uv, vec4( cLodSizeInv, cLodSize ), ceil( lod ) );
		return mix( fSample, cSample, fract( lod ) );
	}
	vec3 getVolumeTransmissionRay( const in vec3 n, const in vec3 v, const in float thickness, const in float ior, const in mat4 modelMatrix ) {
		vec3 refractionVector = refract( - v, normalize( n ), 1.0 / ior );
		vec3 modelScale;
		modelScale.x = length( vec3( modelMatrix[ 0 ].xyz ) );
		modelScale.y = length( vec3( modelMatrix[ 1 ].xyz ) );
		modelScale.z = length( vec3( modelMatrix[ 2 ].xyz ) );
		return normalize( refractionVector ) * thickness * modelScale;
	}
	float applyIorToRoughness( const in float roughness, const in float ior ) {
		return roughness * clamp( ior * 2.0 - 2.0, 0.0, 1.0 );
	}
	vec4 getTransmissionSample( const in vec2 fragCoord, const in float roughness, const in float ior ) {
		float lod = log2( transmissionSamplerSize.x ) * applyIorToRoughness( roughness, ior );
		return textureBicubic( transmissionSamplerMap, fragCoord.xy, lod );
	}
	vec3 volumeAttenuation( const in float transmissionDistance, const in vec3 attenuationColor, const in float attenuationDistance ) {
		if ( isinf( attenuationDistance ) ) {
			return vec3( 1.0 );
		} else {
			vec3 attenuationCoefficient = -log( attenuationColor ) / attenuationDistance;
			vec3 transmittance = exp( - attenuationCoefficient * transmissionDistance );			return transmittance;
		}
	}
	vec4 getIBLVolumeRefraction( const in vec3 n, const in vec3 v, const in float roughness, const in vec3 diffuseColor,
		const in vec3 specularColor, const in float specularF90, const in vec3 position, const in mat4 modelMatrix,
		const in mat4 viewMatrix, const in mat4 projMatrix, const in float dispersion, const in float ior, const in float thickness,
		const in vec3 attenuationColor, const in float attenuationDistance ) {
		vec4 transmittedLight;
		vec3 transmittance;
		#ifdef USE_DISPERSION
			float halfSpread = ( ior - 1.0 ) * 0.025 * dispersion;
			vec3 iors = vec3( ior - halfSpread, ior, ior + halfSpread );
			for ( int i = 0; i < 3; i ++ ) {
				vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, iors[ i ], modelMatrix );
				vec3 refractedRayExit = position + transmissionRay;
				vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
				vec2 refractionCoords = ndcPos.xy / ndcPos.w;
				refractionCoords += 1.0;
				refractionCoords /= 2.0;
				vec4 transmissionSample = getTransmissionSample( refractionCoords, roughness, iors[ i ] );
				transmittedLight[ i ] = transmissionSample[ i ];
				transmittedLight.a += transmissionSample.a;
				transmittance[ i ] = diffuseColor[ i ] * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance )[ i ];
			}
			transmittedLight.a /= 3.0;
		#else
			vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, ior, modelMatrix );
			vec3 refractedRayExit = position + transmissionRay;
			vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
			vec2 refractionCoords = ndcPos.xy / ndcPos.w;
			refractionCoords += 1.0;
			refractionCoords /= 2.0;
			transmittedLight = getTransmissionSample( refractionCoords, roughness, ior );
			transmittance = diffuseColor * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance );
		#endif
		vec3 attenuatedColor = transmittance * transmittedLight.rgb;
		vec3 F = EnvironmentBRDF( n, v, specularColor, specularF90, roughness );
		float transmittanceFactor = ( transmittance.r + transmittance.g + transmittance.b ) / 3.0;
		return vec4( ( 1.0 - F ) * attenuatedColor, 1.0 - ( 1.0 - transmittedLight.a ) * transmittanceFactor );
	}
#endif`,_d=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_SPECULARMAP
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,vd=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	uniform mat3 mapTransform;
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	uniform mat3 alphaMapTransform;
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	uniform mat3 lightMapTransform;
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	uniform mat3 aoMapTransform;
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	uniform mat3 bumpMapTransform;
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	uniform mat3 normalMapTransform;
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_DISPLACEMENTMAP
	uniform mat3 displacementMapTransform;
	varying vec2 vDisplacementMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	uniform mat3 emissiveMapTransform;
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	uniform mat3 metalnessMapTransform;
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	uniform mat3 roughnessMapTransform;
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	uniform mat3 anisotropyMapTransform;
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	uniform mat3 clearcoatMapTransform;
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform mat3 clearcoatNormalMapTransform;
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform mat3 clearcoatRoughnessMapTransform;
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	uniform mat3 sheenColorMapTransform;
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	uniform mat3 sheenRoughnessMapTransform;
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	uniform mat3 iridescenceMapTransform;
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform mat3 iridescenceThicknessMapTransform;
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SPECULARMAP
	uniform mat3 specularMapTransform;
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	uniform mat3 specularColorMapTransform;
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	uniform mat3 specularIntensityMapTransform;
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,xd=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	vUv = vec3( uv, 1 ).xy;
#endif
#ifdef USE_MAP
	vMapUv = ( mapTransform * vec3( MAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ALPHAMAP
	vAlphaMapUv = ( alphaMapTransform * vec3( ALPHAMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_LIGHTMAP
	vLightMapUv = ( lightMapTransform * vec3( LIGHTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_AOMAP
	vAoMapUv = ( aoMapTransform * vec3( AOMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_BUMPMAP
	vBumpMapUv = ( bumpMapTransform * vec3( BUMPMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_NORMALMAP
	vNormalMapUv = ( normalMapTransform * vec3( NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_DISPLACEMENTMAP
	vDisplacementMapUv = ( displacementMapTransform * vec3( DISPLACEMENTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_EMISSIVEMAP
	vEmissiveMapUv = ( emissiveMapTransform * vec3( EMISSIVEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_METALNESSMAP
	vMetalnessMapUv = ( metalnessMapTransform * vec3( METALNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ROUGHNESSMAP
	vRoughnessMapUv = ( roughnessMapTransform * vec3( ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ANISOTROPYMAP
	vAnisotropyMapUv = ( anisotropyMapTransform * vec3( ANISOTROPYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOATMAP
	vClearcoatMapUv = ( clearcoatMapTransform * vec3( CLEARCOATMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	vClearcoatNormalMapUv = ( clearcoatNormalMapTransform * vec3( CLEARCOAT_NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	vClearcoatRoughnessMapUv = ( clearcoatRoughnessMapTransform * vec3( CLEARCOAT_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCEMAP
	vIridescenceMapUv = ( iridescenceMapTransform * vec3( IRIDESCENCEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	vIridescenceThicknessMapUv = ( iridescenceThicknessMapTransform * vec3( IRIDESCENCE_THICKNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_COLORMAP
	vSheenColorMapUv = ( sheenColorMapTransform * vec3( SHEEN_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	vSheenRoughnessMapUv = ( sheenRoughnessMapTransform * vec3( SHEEN_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULARMAP
	vSpecularMapUv = ( specularMapTransform * vec3( SPECULARMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_COLORMAP
	vSpecularColorMapUv = ( specularColorMapTransform * vec3( SPECULAR_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	vSpecularIntensityMapUv = ( specularIntensityMapTransform * vec3( SPECULAR_INTENSITYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_TRANSMISSIONMAP
	vTransmissionMapUv = ( transmissionMapTransform * vec3( TRANSMISSIONMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_THICKNESSMAP
	vThicknessMapUv = ( thicknessMapTransform * vec3( THICKNESSMAP_UV, 1 ) ).xy;
#endif`,Md=`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`;const Sd=`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,yd=`uniform sampler2D t2D;
uniform float backgroundIntensity;
varying vec2 vUv;
void main() {
	vec4 texColor = texture2D( t2D, vUv );
	#ifdef DECODE_VIDEO_TEXTURE
		texColor = vec4( mix( pow( texColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), texColor.rgb * 0.0773993808, vec3( lessThanEqual( texColor.rgb, vec3( 0.04045 ) ) ) ), texColor.w );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Ed=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,Td=`#ifdef ENVMAP_TYPE_CUBE
	uniform samplerCube envMap;
#elif defined( ENVMAP_TYPE_CUBE_UV )
	uniform sampler2D envMap;
#endif
uniform float flipEnvMap;
uniform float backgroundBlurriness;
uniform float backgroundIntensity;
uniform mat3 backgroundRotation;
varying vec3 vWorldDirection;
#include <cube_uv_reflection_fragment>
void main() {
	#ifdef ENVMAP_TYPE_CUBE
		vec4 texColor = textureCube( envMap, backgroundRotation * vec3( flipEnvMap * vWorldDirection.x, vWorldDirection.yz ) );
	#elif defined( ENVMAP_TYPE_CUBE_UV )
		vec4 texColor = textureCubeUV( envMap, backgroundRotation * vWorldDirection, backgroundBlurriness );
	#else
		vec4 texColor = vec4( 0.0, 0.0, 0.0, 1.0 );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,bd=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,Ad=`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,wd=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
varying vec2 vHighPrecisionZW;
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vHighPrecisionZW = gl_Position.zw;
}`,Rd=`#if DEPTH_PACKING == 3200
	uniform float opacity;
#endif
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
varying vec2 vHighPrecisionZW;
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#if DEPTH_PACKING == 3200
		diffuseColor.a = opacity;
	#endif
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <logdepthbuf_fragment>
	#ifdef USE_REVERSEDEPTHBUF
		float fragCoordZ = vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ];
	#else
		float fragCoordZ = 0.5 * vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ] + 0.5;
	#endif
	#if DEPTH_PACKING == 3200
		gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );
	#elif DEPTH_PACKING == 3201
		gl_FragColor = packDepthToRGBA( fragCoordZ );
	#elif DEPTH_PACKING == 3202
		gl_FragColor = vec4( packDepthToRGB( fragCoordZ ), 1.0 );
	#elif DEPTH_PACKING == 3203
		gl_FragColor = vec4( packDepthToRG( fragCoordZ ), 0.0, 1.0 );
	#endif
}`,Cd=`#define DISTANCE
varying vec3 vWorldPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <worldpos_vertex>
	#include <clipping_planes_vertex>
	vWorldPosition = worldPosition.xyz;
}`,Pd=`#define DISTANCE
uniform vec3 referencePosition;
uniform float nearDistance;
uniform float farDistance;
varying vec3 vWorldPosition;
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <clipping_planes_pars_fragment>
void main () {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	float dist = length( vWorldPosition - referencePosition );
	dist = ( dist - nearDistance ) / ( farDistance - nearDistance );
	dist = saturate( dist );
	gl_FragColor = packDepthToRGBA( dist );
}`,Dd=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,Ld=`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Ud=`uniform float scale;
attribute float lineDistance;
varying float vLineDistance;
#include <common>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	vLineDistance = scale * lineDistance;
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,Id=`uniform vec3 diffuse;
uniform float opacity;
uniform float dashSize;
uniform float totalSize;
varying float vLineDistance;
#include <common>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	if ( mod( vLineDistance, totalSize ) > dashSize ) {
		discard;
	}
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,Nd=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinbase_vertex>
		#include <skinnormal_vertex>
		#include <defaultnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <fog_vertex>
}`,Fd=`uniform vec3 diffuse;
uniform float opacity;
#ifndef FLAT_SHADED
	varying vec3 vNormal;
#endif
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		reflectedLight.indirectDiffuse += lightMapTexel.rgb * lightMapIntensity * RECIPROCAL_PI;
	#else
		reflectedLight.indirectDiffuse += vec3( 1.0 );
	#endif
	#include <aomap_fragment>
	reflectedLight.indirectDiffuse *= diffuseColor.rgb;
	vec3 outgoingLight = reflectedLight.indirectDiffuse;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Od=`#define LAMBERT
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Bd=`#define LAMBERT
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_lambert_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_lambert_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,zd=`#define MATCAP
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <displacementmap_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
	vViewPosition = - mvPosition.xyz;
}`,Hd=`#define MATCAP
uniform vec3 diffuse;
uniform float opacity;
uniform sampler2D matcap;
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	vec3 viewDir = normalize( vViewPosition );
	vec3 x = normalize( vec3( viewDir.z, 0.0, - viewDir.x ) );
	vec3 y = cross( viewDir, x );
	vec2 uv = vec2( dot( x, normal ), dot( y, normal ) ) * 0.495 + 0.5;
	#ifdef USE_MATCAP
		vec4 matcapColor = texture2D( matcap, uv );
	#else
		vec4 matcapColor = vec4( vec3( mix( 0.2, 0.8, uv.y ) ), 1.0 );
	#endif
	vec3 outgoingLight = diffuseColor.rgb * matcapColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,kd=`#define NORMAL
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	vViewPosition = - mvPosition.xyz;
#endif
}`,Vd=`#define NORMAL
uniform float opacity;
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <packing>
#include <uv_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 0.0, 0.0, 0.0, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	gl_FragColor = vec4( packNormalToRGB( normal ), diffuseColor.a );
	#ifdef OPAQUE
		gl_FragColor.a = 1.0;
	#endif
}`,Gd=`#define PHONG
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Wd=`#define PHONG
uniform vec3 diffuse;
uniform vec3 emissive;
uniform vec3 specular;
uniform float shininess;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_phong_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_phong_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + reflectedLight.directSpecular + reflectedLight.indirectSpecular + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Xd=`#define STANDARD
varying vec3 vViewPosition;
#ifdef USE_TRANSMISSION
	varying vec3 vWorldPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
#ifdef USE_TRANSMISSION
	vWorldPosition = worldPosition.xyz;
#endif
}`,qd=`#define STANDARD
#ifdef PHYSICAL
	#define IOR
	#define USE_SPECULAR
#endif
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float roughness;
uniform float metalness;
uniform float opacity;
#ifdef IOR
	uniform float ior;
#endif
#ifdef USE_SPECULAR
	uniform float specularIntensity;
	uniform vec3 specularColor;
	#ifdef USE_SPECULAR_COLORMAP
		uniform sampler2D specularColorMap;
	#endif
	#ifdef USE_SPECULAR_INTENSITYMAP
		uniform sampler2D specularIntensityMap;
	#endif
#endif
#ifdef USE_CLEARCOAT
	uniform float clearcoat;
	uniform float clearcoatRoughness;
#endif
#ifdef USE_DISPERSION
	uniform float dispersion;
#endif
#ifdef USE_IRIDESCENCE
	uniform float iridescence;
	uniform float iridescenceIOR;
	uniform float iridescenceThicknessMinimum;
	uniform float iridescenceThicknessMaximum;
#endif
#ifdef USE_SHEEN
	uniform vec3 sheenColor;
	uniform float sheenRoughness;
	#ifdef USE_SHEEN_COLORMAP
		uniform sampler2D sheenColorMap;
	#endif
	#ifdef USE_SHEEN_ROUGHNESSMAP
		uniform sampler2D sheenRoughnessMap;
	#endif
#endif
#ifdef USE_ANISOTROPY
	uniform vec2 anisotropyVector;
	#ifdef USE_ANISOTROPYMAP
		uniform sampler2D anisotropyMap;
	#endif
#endif
varying vec3 vViewPosition;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <iridescence_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_physical_pars_fragment>
#include <transmission_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <clearcoat_pars_fragment>
#include <iridescence_pars_fragment>
#include <roughnessmap_pars_fragment>
#include <metalnessmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <roughnessmap_fragment>
	#include <metalnessmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <clearcoat_normal_fragment_begin>
	#include <clearcoat_normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_physical_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 totalDiffuse = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
	vec3 totalSpecular = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
	#include <transmission_fragment>
	vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;
	#ifdef USE_SHEEN
		float sheenEnergyComp = 1.0 - 0.157 * max3( material.sheenColor );
		outgoingLight = outgoingLight * sheenEnergyComp + sheenSpecularDirect + sheenSpecularIndirect;
	#endif
	#ifdef USE_CLEARCOAT
		float dotNVcc = saturate( dot( geometryClearcoatNormal, geometryViewDir ) );
		vec3 Fcc = F_Schlick( material.clearcoatF0, material.clearcoatF90, dotNVcc );
		outgoingLight = outgoingLight * ( 1.0 - material.clearcoat * Fcc ) + ( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat;
	#endif
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Yd=`#define TOON
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,jd=`#define TOON
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <gradientmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_toon_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_toon_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Kd=`uniform float size;
uniform float scale;
#include <common>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
#ifdef USE_POINTS_UV
	varying vec2 vUv;
	uniform mat3 uvTransform;
#endif
void main() {
	#ifdef USE_POINTS_UV
		vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	#endif
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	gl_PointSize = size;
	#ifdef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) gl_PointSize *= ( scale / - mvPosition.z );
	#endif
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <fog_vertex>
}`,Zd=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <color_pars_fragment>
#include <map_particle_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_particle_fragment>
	#include <color_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,$d=`#include <common>
#include <batching_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
void main() {
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Jd=`uniform vec3 color;
uniform float opacity;
#include <common>
#include <packing>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <logdepthbuf_pars_fragment>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
void main() {
	#include <logdepthbuf_fragment>
	gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,Qd=`uniform float rotation;
uniform vec2 center;
#include <common>
#include <uv_pars_vertex>
#include <fog_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	vec4 mvPosition = modelViewMatrix[ 3 ];
	vec2 scale = vec2( length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ) );
	#ifndef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) scale *= - mvPosition.z;
	#endif
	vec2 alignedPosition = ( position.xy - ( center - vec2( 0.5 ) ) ) * scale;
	vec2 rotatedPosition;
	rotatedPosition.x = cos( rotation ) * alignedPosition.x - sin( rotation ) * alignedPosition.y;
	rotatedPosition.y = sin( rotation ) * alignedPosition.x + cos( rotation ) * alignedPosition.y;
	mvPosition.xy += rotatedPosition;
	gl_Position = projectionMatrix * mvPosition;
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,ef=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,et={alphahash_fragment:yu,alphahash_pars_fragment:Eu,alphamap_fragment:Tu,alphamap_pars_fragment:bu,alphatest_fragment:Au,alphatest_pars_fragment:wu,aomap_fragment:Ru,aomap_pars_fragment:Cu,batching_pars_vertex:Pu,batching_vertex:Du,begin_vertex:Lu,beginnormal_vertex:Uu,bsdfs:Iu,iridescence_fragment:Nu,bumpmap_pars_fragment:Fu,clipping_planes_fragment:Ou,clipping_planes_pars_fragment:Bu,clipping_planes_pars_vertex:zu,clipping_planes_vertex:Hu,color_fragment:ku,color_pars_fragment:Vu,color_pars_vertex:Gu,color_vertex:Wu,common:Xu,cube_uv_reflection_fragment:qu,defaultnormal_vertex:Yu,displacementmap_pars_vertex:ju,displacementmap_vertex:Ku,emissivemap_fragment:Zu,emissivemap_pars_fragment:$u,colorspace_fragment:Ju,colorspace_pars_fragment:Qu,envmap_fragment:eh,envmap_common_pars_fragment:th,envmap_pars_fragment:nh,envmap_pars_vertex:ih,envmap_physical_pars_fragment:ph,envmap_vertex:rh,fog_vertex:sh,fog_pars_vertex:oh,fog_fragment:ah,fog_pars_fragment:lh,gradientmap_pars_fragment:ch,lightmap_pars_fragment:uh,lights_lambert_fragment:hh,lights_lambert_pars_fragment:dh,lights_pars_begin:fh,lights_toon_fragment:mh,lights_toon_pars_fragment:gh,lights_phong_fragment:_h,lights_phong_pars_fragment:vh,lights_physical_fragment:xh,lights_physical_pars_fragment:Mh,lights_fragment_begin:Sh,lights_fragment_maps:yh,lights_fragment_end:Eh,logdepthbuf_fragment:Th,logdepthbuf_pars_fragment:bh,logdepthbuf_pars_vertex:Ah,logdepthbuf_vertex:wh,map_fragment:Rh,map_pars_fragment:Ch,map_particle_fragment:Ph,map_particle_pars_fragment:Dh,metalnessmap_fragment:Lh,metalnessmap_pars_fragment:Uh,morphinstance_vertex:Ih,morphcolor_vertex:Nh,morphnormal_vertex:Fh,morphtarget_pars_vertex:Oh,morphtarget_vertex:Bh,normal_fragment_begin:zh,normal_fragment_maps:Hh,normal_pars_fragment:kh,normal_pars_vertex:Vh,normal_vertex:Gh,normalmap_pars_fragment:Wh,clearcoat_normal_fragment_begin:Xh,clearcoat_normal_fragment_maps:qh,clearcoat_pars_fragment:Yh,iridescence_pars_fragment:jh,opaque_fragment:Kh,packing:Zh,premultiplied_alpha_fragment:$h,project_vertex:Jh,dithering_fragment:Qh,dithering_pars_fragment:ed,roughnessmap_fragment:td,roughnessmap_pars_fragment:nd,shadowmap_pars_fragment:id,shadowmap_pars_vertex:rd,shadowmap_vertex:sd,shadowmask_pars_fragment:od,skinbase_vertex:ad,skinning_pars_vertex:ld,skinning_vertex:cd,skinnormal_vertex:ud,specularmap_fragment:hd,specularmap_pars_fragment:dd,tonemapping_fragment:fd,tonemapping_pars_fragment:pd,transmission_fragment:md,transmission_pars_fragment:gd,uv_pars_fragment:_d,uv_pars_vertex:vd,uv_vertex:xd,worldpos_vertex:Md,background_vert:Sd,background_frag:yd,backgroundCube_vert:Ed,backgroundCube_frag:Td,cube_vert:bd,cube_frag:Ad,depth_vert:wd,depth_frag:Rd,distanceRGBA_vert:Cd,distanceRGBA_frag:Pd,equirect_vert:Dd,equirect_frag:Ld,linedashed_vert:Ud,linedashed_frag:Id,meshbasic_vert:Nd,meshbasic_frag:Fd,meshlambert_vert:Od,meshlambert_frag:Bd,meshmatcap_vert:zd,meshmatcap_frag:Hd,meshnormal_vert:kd,meshnormal_frag:Vd,meshphong_vert:Gd,meshphong_frag:Wd,meshphysical_vert:Xd,meshphysical_frag:qd,meshtoon_vert:Yd,meshtoon_frag:jd,points_vert:Kd,points_frag:Zd,shadow_vert:$d,shadow_frag:Jd,sprite_vert:Qd,sprite_frag:ef},Se={common:{diffuse:{value:new je(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new Qe},alphaMap:{value:null},alphaMapTransform:{value:new Qe},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new Qe}},envmap:{envMap:{value:null},envMapRotation:{value:new Qe},flipEnvMap:{value:-1},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new Qe}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new Qe}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new Qe},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new Qe},normalScale:{value:new Ye(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new Qe},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new Qe}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new Qe}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new Qe}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new je(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMap:{value:[]},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotShadowMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMap:{value:[]},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null}},points:{diffuse:{value:new je(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new Qe},alphaTest:{value:0},uvTransform:{value:new Qe}},sprite:{diffuse:{value:new je(16777215)},opacity:{value:1},center:{value:new Ye(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new Qe},alphaMap:{value:null},alphaMapTransform:{value:new Qe},alphaTest:{value:0}}},pn={basic:{uniforms:Nt([Se.common,Se.specularmap,Se.envmap,Se.aomap,Se.lightmap,Se.fog]),vertexShader:et.meshbasic_vert,fragmentShader:et.meshbasic_frag},lambert:{uniforms:Nt([Se.common,Se.specularmap,Se.envmap,Se.aomap,Se.lightmap,Se.emissivemap,Se.bumpmap,Se.normalmap,Se.displacementmap,Se.fog,Se.lights,{emissive:{value:new je(0)}}]),vertexShader:et.meshlambert_vert,fragmentShader:et.meshlambert_frag},phong:{uniforms:Nt([Se.common,Se.specularmap,Se.envmap,Se.aomap,Se.lightmap,Se.emissivemap,Se.bumpmap,Se.normalmap,Se.displacementmap,Se.fog,Se.lights,{emissive:{value:new je(0)},specular:{value:new je(1118481)},shininess:{value:30}}]),vertexShader:et.meshphong_vert,fragmentShader:et.meshphong_frag},standard:{uniforms:Nt([Se.common,Se.envmap,Se.aomap,Se.lightmap,Se.emissivemap,Se.bumpmap,Se.normalmap,Se.displacementmap,Se.roughnessmap,Se.metalnessmap,Se.fog,Se.lights,{emissive:{value:new je(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:et.meshphysical_vert,fragmentShader:et.meshphysical_frag},toon:{uniforms:Nt([Se.common,Se.aomap,Se.lightmap,Se.emissivemap,Se.bumpmap,Se.normalmap,Se.displacementmap,Se.gradientmap,Se.fog,Se.lights,{emissive:{value:new je(0)}}]),vertexShader:et.meshtoon_vert,fragmentShader:et.meshtoon_frag},matcap:{uniforms:Nt([Se.common,Se.bumpmap,Se.normalmap,Se.displacementmap,Se.fog,{matcap:{value:null}}]),vertexShader:et.meshmatcap_vert,fragmentShader:et.meshmatcap_frag},points:{uniforms:Nt([Se.points,Se.fog]),vertexShader:et.points_vert,fragmentShader:et.points_frag},dashed:{uniforms:Nt([Se.common,Se.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:et.linedashed_vert,fragmentShader:et.linedashed_frag},depth:{uniforms:Nt([Se.common,Se.displacementmap]),vertexShader:et.depth_vert,fragmentShader:et.depth_frag},normal:{uniforms:Nt([Se.common,Se.bumpmap,Se.normalmap,Se.displacementmap,{opacity:{value:1}}]),vertexShader:et.meshnormal_vert,fragmentShader:et.meshnormal_frag},sprite:{uniforms:Nt([Se.sprite,Se.fog]),vertexShader:et.sprite_vert,fragmentShader:et.sprite_frag},background:{uniforms:{uvTransform:{value:new Qe},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:et.background_vert,fragmentShader:et.background_frag},backgroundCube:{uniforms:{envMap:{value:null},flipEnvMap:{value:-1},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new Qe}},vertexShader:et.backgroundCube_vert,fragmentShader:et.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:et.cube_vert,fragmentShader:et.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:et.equirect_vert,fragmentShader:et.equirect_frag},distanceRGBA:{uniforms:Nt([Se.common,Se.displacementmap,{referencePosition:{value:new B},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:et.distanceRGBA_vert,fragmentShader:et.distanceRGBA_frag},shadow:{uniforms:Nt([Se.lights,Se.fog,{color:{value:new je(0)},opacity:{value:1}}]),vertexShader:et.shadow_vert,fragmentShader:et.shadow_frag}};pn.physical={uniforms:Nt([pn.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new Qe},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new Qe},clearcoatNormalScale:{value:new Ye(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new Qe},dispersion:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new Qe},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new Qe},sheen:{value:0},sheenColor:{value:new je(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new Qe},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new Qe},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new Qe},transmissionSamplerSize:{value:new Ye},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new Qe},attenuationDistance:{value:0},attenuationColor:{value:new je(0)},specularColor:{value:new je(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new Qe},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new Qe},anisotropyVector:{value:new Ye},anisotropyMap:{value:null},anisotropyMapTransform:{value:new Qe}}]),vertexShader:et.meshphysical_vert,fragmentShader:et.meshphysical_frag};const Ir={r:0,b:0,g:0},Zn=new fn,tf=new gt;function nf(i,e,t,n,r,s,o){const a=new je(0);let u=s===!0?0:1,l,d,h=null,f=0,m=null;function _(S){let M=S.isScene===!0?S.background:null;return M&&M.isTexture&&(M=(S.backgroundBlurriness>0?t:e).get(M)),M}function v(S){let M=!1;const C=_(S);C===null?c(a,u):C&&C.isColor&&(c(C,1),M=!0);const R=i.xr.getEnvironmentBlendMode();R==="additive"?n.buffers.color.setClear(0,0,0,1,o):R==="alpha-blend"&&n.buffers.color.setClear(0,0,0,0,o),(i.autoClear||M)&&(n.buffers.depth.setTest(!0),n.buffers.depth.setMask(!0),n.buffers.color.setMask(!0),i.clear(i.autoClearColor,i.autoClearDepth,i.autoClearStencil))}function p(S,M){const C=_(M);C&&(C.isCubeTexture||C.mapping===jr)?(d===void 0&&(d=new Ft(new lr(1,1,1),new Gn({name:"BackgroundCubeMaterial",uniforms:Oi(pn.backgroundCube.uniforms),vertexShader:pn.backgroundCube.vertexShader,fragmentShader:pn.backgroundCube.fragmentShader,side:Wt,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),d.geometry.deleteAttribute("normal"),d.geometry.deleteAttribute("uv"),d.onBeforeRender=function(R,P,I){this.matrixWorld.copyPosition(I.matrixWorld)},Object.defineProperty(d.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),r.update(d)),Zn.copy(M.backgroundRotation),Zn.x*=-1,Zn.y*=-1,Zn.z*=-1,C.isCubeTexture&&C.isRenderTargetTexture===!1&&(Zn.y*=-1,Zn.z*=-1),d.material.uniforms.envMap.value=C,d.material.uniforms.flipEnvMap.value=C.isCubeTexture&&C.isRenderTargetTexture===!1?-1:1,d.material.uniforms.backgroundBlurriness.value=M.backgroundBlurriness,d.material.uniforms.backgroundIntensity.value=M.backgroundIntensity,d.material.uniforms.backgroundRotation.value.setFromMatrix4(tf.makeRotationFromEuler(Zn)),d.material.toneMapped=at.getTransfer(C.colorSpace)!==ht,(h!==C||f!==C.version||m!==i.toneMapping)&&(d.material.needsUpdate=!0,h=C,f=C.version,m=i.toneMapping),d.layers.enableAll(),S.unshift(d,d.geometry,d.material,0,0,null)):C&&C.isTexture&&(l===void 0&&(l=new Ft(new $r(2,2),new Gn({name:"BackgroundMaterial",uniforms:Oi(pn.background.uniforms),vertexShader:pn.background.vertexShader,fragmentShader:pn.background.fragmentShader,side:Vn,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),l.geometry.deleteAttribute("normal"),Object.defineProperty(l.material,"map",{get:function(){return this.uniforms.t2D.value}}),r.update(l)),l.material.uniforms.t2D.value=C,l.material.uniforms.backgroundIntensity.value=M.backgroundIntensity,l.material.toneMapped=at.getTransfer(C.colorSpace)!==ht,C.matrixAutoUpdate===!0&&C.updateMatrix(),l.material.uniforms.uvTransform.value.copy(C.matrix),(h!==C||f!==C.version||m!==i.toneMapping)&&(l.material.needsUpdate=!0,h=C,f=C.version,m=i.toneMapping),l.layers.enableAll(),S.unshift(l,l.geometry,l.material,0,0,null))}function c(S,M){S.getRGB(Ir,vl(i)),n.buffers.color.setClear(Ir.r,Ir.g,Ir.b,M,o)}function A(){d!==void 0&&(d.geometry.dispose(),d.material.dispose(),d=void 0),l!==void 0&&(l.geometry.dispose(),l.material.dispose(),l=void 0)}return{getClearColor:function(){return a},setClearColor:function(S,M=1){a.set(S),u=M,c(a,u)},getClearAlpha:function(){return u},setClearAlpha:function(S){u=S,c(a,u)},render:v,addToRenderList:p,dispose:A}}function rf(i,e){const t=i.getParameter(i.MAX_VERTEX_ATTRIBS),n={},r=f(null);let s=r,o=!1;function a(E,w,Q,j,Z){let re=!1;const X=h(j,Q,w);s!==X&&(s=X,l(s.object)),re=m(E,j,Q,Z),re&&_(E,j,Q,Z),Z!==null&&e.update(Z,i.ELEMENT_ARRAY_BUFFER),(re||o)&&(o=!1,M(E,w,Q,j),Z!==null&&i.bindBuffer(i.ELEMENT_ARRAY_BUFFER,e.get(Z).buffer))}function u(){return i.createVertexArray()}function l(E){return i.bindVertexArray(E)}function d(E){return i.deleteVertexArray(E)}function h(E,w,Q){const j=Q.wireframe===!0;let Z=n[E.id];Z===void 0&&(Z={},n[E.id]=Z);let re=Z[w.id];re===void 0&&(re={},Z[w.id]=re);let X=re[j];return X===void 0&&(X=f(u()),re[j]=X),X}function f(E){const w=[],Q=[],j=[];for(let Z=0;Z<t;Z++)w[Z]=0,Q[Z]=0,j[Z]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:w,enabledAttributes:Q,attributeDivisors:j,object:E,attributes:{},index:null}}function m(E,w,Q,j){const Z=s.attributes,re=w.attributes;let X=0;const ae=Q.getAttributes();for(const W in ae)if(ae[W].location>=0){const ye=Z[W];let Te=re[W];if(Te===void 0&&(W==="instanceMatrix"&&E.instanceMatrix&&(Te=E.instanceMatrix),W==="instanceColor"&&E.instanceColor&&(Te=E.instanceColor)),ye===void 0||ye.attribute!==Te||Te&&ye.data!==Te.data)return!0;X++}return s.attributesNum!==X||s.index!==j}function _(E,w,Q,j){const Z={},re=w.attributes;let X=0;const ae=Q.getAttributes();for(const W in ae)if(ae[W].location>=0){let ye=re[W];ye===void 0&&(W==="instanceMatrix"&&E.instanceMatrix&&(ye=E.instanceMatrix),W==="instanceColor"&&E.instanceColor&&(ye=E.instanceColor));const Te={};Te.attribute=ye,ye&&ye.data&&(Te.data=ye.data),Z[W]=Te,X++}s.attributes=Z,s.attributesNum=X,s.index=j}function v(){const E=s.newAttributes;for(let w=0,Q=E.length;w<Q;w++)E[w]=0}function p(E){c(E,0)}function c(E,w){const Q=s.newAttributes,j=s.enabledAttributes,Z=s.attributeDivisors;Q[E]=1,j[E]===0&&(i.enableVertexAttribArray(E),j[E]=1),Z[E]!==w&&(i.vertexAttribDivisor(E,w),Z[E]=w)}function A(){const E=s.newAttributes,w=s.enabledAttributes;for(let Q=0,j=w.length;Q<j;Q++)w[Q]!==E[Q]&&(i.disableVertexAttribArray(Q),w[Q]=0)}function S(E,w,Q,j,Z,re,X){X===!0?i.vertexAttribIPointer(E,w,Q,Z,re):i.vertexAttribPointer(E,w,Q,j,Z,re)}function M(E,w,Q,j){v();const Z=j.attributes,re=Q.getAttributes(),X=w.defaultAttributeValues;for(const ae in re){const W=re[ae];if(W.location>=0){let he=Z[ae];if(he===void 0&&(ae==="instanceMatrix"&&E.instanceMatrix&&(he=E.instanceMatrix),ae==="instanceColor"&&E.instanceColor&&(he=E.instanceColor)),he!==void 0){const ye=he.normalized,Te=he.itemSize,ze=e.get(he);if(ze===void 0)continue;const nt=ze.buffer,it=ze.type,J=ze.bytesPerElement,L=it===i.INT||it===i.UNSIGNED_INT||he.gpuType===Co;if(he.isInterleavedBufferAttribute){const D=he.data,z=D.stride,H=he.offset;if(D.isInstancedInterleavedBuffer){for(let G=0;G<W.locationSize;G++)c(W.location+G,D.meshPerAttribute);E.isInstancedMesh!==!0&&j._maxInstanceCount===void 0&&(j._maxInstanceCount=D.meshPerAttribute*D.count)}else for(let G=0;G<W.locationSize;G++)p(W.location+G);i.bindBuffer(i.ARRAY_BUFFER,nt);for(let G=0;G<W.locationSize;G++)S(W.location+G,Te/W.locationSize,it,ye,z*J,(H+Te/W.locationSize*G)*J,L)}else{if(he.isInstancedBufferAttribute){for(let D=0;D<W.locationSize;D++)c(W.location+D,he.meshPerAttribute);E.isInstancedMesh!==!0&&j._maxInstanceCount===void 0&&(j._maxInstanceCount=he.meshPerAttribute*he.count)}else for(let D=0;D<W.locationSize;D++)p(W.location+D);i.bindBuffer(i.ARRAY_BUFFER,nt);for(let D=0;D<W.locationSize;D++)S(W.location+D,Te/W.locationSize,it,ye,Te*J,Te/W.locationSize*D*J,L)}}else if(X!==void 0){const ye=X[ae];if(ye!==void 0)switch(ye.length){case 2:i.vertexAttrib2fv(W.location,ye);break;case 3:i.vertexAttrib3fv(W.location,ye);break;case 4:i.vertexAttrib4fv(W.location,ye);break;default:i.vertexAttrib1fv(W.location,ye)}}}}A()}function C(){I();for(const E in n){const w=n[E];for(const Q in w){const j=w[Q];for(const Z in j)d(j[Z].object),delete j[Z];delete w[Q]}delete n[E]}}function R(E){if(n[E.id]===void 0)return;const w=n[E.id];for(const Q in w){const j=w[Q];for(const Z in j)d(j[Z].object),delete j[Z];delete w[Q]}delete n[E.id]}function P(E){for(const w in n){const Q=n[w];if(Q[E.id]===void 0)continue;const j=Q[E.id];for(const Z in j)d(j[Z].object),delete j[Z];delete Q[E.id]}}function I(){y(),o=!0,s!==r&&(s=r,l(s.object))}function y(){r.geometry=null,r.program=null,r.wireframe=!1}return{setup:a,reset:I,resetDefaultState:y,dispose:C,releaseStatesOfGeometry:R,releaseStatesOfProgram:P,initAttributes:v,enableAttribute:p,disableUnusedAttributes:A}}function sf(i,e,t){let n;function r(l){n=l}function s(l,d){i.drawArrays(n,l,d),t.update(d,n,1)}function o(l,d,h){h!==0&&(i.drawArraysInstanced(n,l,d,h),t.update(d,n,h))}function a(l,d,h){if(h===0)return;e.get("WEBGL_multi_draw").multiDrawArraysWEBGL(n,l,0,d,0,h);let m=0;for(let _=0;_<h;_++)m+=d[_];t.update(m,n,1)}function u(l,d,h,f){if(h===0)return;const m=e.get("WEBGL_multi_draw");if(m===null)for(let _=0;_<l.length;_++)o(l[_],d[_],f[_]);else{m.multiDrawArraysInstancedWEBGL(n,l,0,d,0,f,0,h);let _=0;for(let v=0;v<h;v++)_+=d[v]*f[v];t.update(_,n,1)}}this.setMode=r,this.render=s,this.renderInstances=o,this.renderMultiDraw=a,this.renderMultiDrawInstances=u}function of(i,e,t,n){let r;function s(){if(r!==void 0)return r;if(e.has("EXT_texture_filter_anisotropic")===!0){const P=e.get("EXT_texture_filter_anisotropic");r=i.getParameter(P.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else r=0;return r}function o(P){return!(P!==dn&&n.convert(P)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_FORMAT))}function a(P){const I=P===or&&(e.has("EXT_color_buffer_half_float")||e.has("EXT_color_buffer_float"));return!(P!==_n&&n.convert(P)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_TYPE)&&P!==Cn&&!I)}function u(P){if(P==="highp"){if(i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.HIGH_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.HIGH_FLOAT).precision>0)return"highp";P="mediump"}return P==="mediump"&&i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.MEDIUM_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.MEDIUM_FLOAT).precision>0?"mediump":"lowp"}let l=t.precision!==void 0?t.precision:"highp";const d=u(l);d!==l&&(console.warn("THREE.WebGLRenderer:",l,"not supported, using",d,"instead."),l=d);const h=t.logarithmicDepthBuffer===!0,f=t.reversedDepthBuffer===!0&&e.has("EXT_clip_control"),m=i.getParameter(i.MAX_TEXTURE_IMAGE_UNITS),_=i.getParameter(i.MAX_VERTEX_TEXTURE_IMAGE_UNITS),v=i.getParameter(i.MAX_TEXTURE_SIZE),p=i.getParameter(i.MAX_CUBE_MAP_TEXTURE_SIZE),c=i.getParameter(i.MAX_VERTEX_ATTRIBS),A=i.getParameter(i.MAX_VERTEX_UNIFORM_VECTORS),S=i.getParameter(i.MAX_VARYING_VECTORS),M=i.getParameter(i.MAX_FRAGMENT_UNIFORM_VECTORS),C=_>0,R=i.getParameter(i.MAX_SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:s,getMaxPrecision:u,textureFormatReadable:o,textureTypeReadable:a,precision:l,logarithmicDepthBuffer:h,reversedDepthBuffer:f,maxTextures:m,maxVertexTextures:_,maxTextureSize:v,maxCubemapSize:p,maxAttributes:c,maxVertexUniforms:A,maxVaryings:S,maxFragmentUniforms:M,vertexTextures:C,maxSamples:R}}function af(i){const e=this;let t=null,n=0,r=!1,s=!1;const o=new bn,a=new Qe,u={value:null,needsUpdate:!1};this.uniform=u,this.numPlanes=0,this.numIntersection=0,this.init=function(h,f){const m=h.length!==0||f||n!==0||r;return r=f,n=h.length,m},this.beginShadows=function(){s=!0,d(null)},this.endShadows=function(){s=!1},this.setGlobalState=function(h,f){t=d(h,f,0)},this.setState=function(h,f,m){const _=h.clippingPlanes,v=h.clipIntersection,p=h.clipShadows,c=i.get(h);if(!r||_===null||_.length===0||s&&!p)s?d(null):l();else{const A=s?0:n,S=A*4;let M=c.clippingState||null;u.value=M,M=d(_,f,S,m);for(let C=0;C!==S;++C)M[C]=t[C];c.clippingState=M,this.numIntersection=v?this.numPlanes:0,this.numPlanes+=A}};function l(){u.value!==t&&(u.value=t,u.needsUpdate=n>0),e.numPlanes=n,e.numIntersection=0}function d(h,f,m,_){const v=h!==null?h.length:0;let p=null;if(v!==0){if(p=u.value,_!==!0||p===null){const c=m+v*4,A=f.matrixWorldInverse;a.getNormalMatrix(A),(p===null||p.length<c)&&(p=new Float32Array(c));for(let S=0,M=m;S!==v;++S,M+=4)o.copy(h[S]).applyMatrix4(A,a),o.normal.toArray(p,M),p[M+3]=o.constant}u.value=p,u.needsUpdate=!0}return e.numPlanes=v,e.numIntersection=0,p}}function lf(i){let e=new WeakMap;function t(o,a){return a===Ys?o.mapping=Ii:a===js&&(o.mapping=Ni),o}function n(o){if(o&&o.isTexture){const a=o.mapping;if(a===Ys||a===js)if(e.has(o)){const u=e.get(o).texture;return t(u,o.mapping)}else{const u=o.image;if(u&&u.height>0){const l=new Jc(u.height);return l.fromEquirectangularTexture(i,o),e.set(o,l),o.addEventListener("dispose",r),t(l.texture,o.mapping)}else return null}}return o}function r(o){const a=o.target;a.removeEventListener("dispose",r);const u=e.get(a);u!==void 0&&(e.delete(a),u.dispose())}function s(){e=new WeakMap}return{get:n,dispose:s}}const wi=4,wa=[.125,.215,.35,.446,.526,.582],ei=20,ws=new bl,Ra=new je;let Rs=null,Cs=0,Ps=0,Ds=!1;const Jn=(1+Math.sqrt(5))/2,bi=1/Jn,Ca=[new B(-Jn,bi,0),new B(Jn,bi,0),new B(-bi,0,Jn),new B(bi,0,Jn),new B(0,Jn,-bi),new B(0,Jn,bi),new B(-1,1,-1),new B(1,1,-1),new B(-1,1,1),new B(1,1,1)],cf=new B;class Pa{constructor(e){this._renderer=e,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._lodPlanes=[],this._sizeLods=[],this._sigmas=[],this._blurMaterial=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._compileMaterial(this._blurMaterial)}fromScene(e,t=0,n=.1,r=100,s={}){const{size:o=256,position:a=cf}=s;Rs=this._renderer.getRenderTarget(),Cs=this._renderer.getActiveCubeFace(),Ps=this._renderer.getActiveMipmapLevel(),Ds=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(o);const u=this._allocateTargets();return u.depthBuffer=!0,this._sceneToCubeUV(e,n,r,u,a),t>0&&this._blur(u,0,0,t),this._applyPMREM(u),this._cleanup(u),u}fromEquirectangular(e,t=null){return this._fromTexture(e,t)}fromCubemap(e,t=null){return this._fromTexture(e,t)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=Ua(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=La(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose()}_setSize(e){this._lodMax=Math.floor(Math.log2(e)),this._cubeSize=Math.pow(2,this._lodMax)}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let e=0;e<this._lodPlanes.length;e++)this._lodPlanes[e].dispose()}_cleanup(e){this._renderer.setRenderTarget(Rs,Cs,Ps),this._renderer.xr.enabled=Ds,e.scissorTest=!1,Nr(e,0,0,e.width,e.height)}_fromTexture(e,t){e.mapping===Ii||e.mapping===Ni?this._setSize(e.image.length===0?16:e.image[0].width||e.image[0].image.width):this._setSize(e.image.width/4),Rs=this._renderer.getRenderTarget(),Cs=this._renderer.getActiveCubeFace(),Ps=this._renderer.getActiveMipmapLevel(),Ds=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;const n=t||this._allocateTargets();return this._textureToCubeUV(e,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){const e=3*Math.max(this._cubeSize,112),t=4*this._cubeSize,n={magFilter:Gt,minFilter:Gt,generateMipmaps:!1,type:or,format:dn,colorSpace:Fi,depthBuffer:!1},r=Da(e,t,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==e||this._pingPongRenderTarget.height!==t){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=Da(e,t,n);const{_lodMax:s}=this;({sizeLods:this._sizeLods,lodPlanes:this._lodPlanes,sigmas:this._sigmas}=uf(s)),this._blurMaterial=hf(s,e,t)}return r}_compileMaterial(e){const t=new Ft(this._lodPlanes[0],e);this._renderer.compile(t,ws)}_sceneToCubeUV(e,t,n,r,s){const u=new sn(90,1,t,n),l=[1,-1,1,1,1,1],d=[1,1,1,-1,-1,-1],h=this._renderer,f=h.autoClear,m=h.toneMapping;h.getClearColor(Ra),h.toneMapping=kn,h.autoClear=!1,h.state.buffers.depth.getReversed()&&(h.setRenderTarget(r),h.clearDepth(),h.setRenderTarget(null));const v=new Bo({name:"PMREM.Background",side:Wt,depthWrite:!1,depthTest:!1}),p=new Ft(new lr,v);let c=!1;const A=e.background;A?A.isColor&&(v.color.copy(A),e.background=null,c=!0):(v.color.copy(Ra),c=!0);for(let S=0;S<6;S++){const M=S%3;M===0?(u.up.set(0,l[S],0),u.position.set(s.x,s.y,s.z),u.lookAt(s.x+d[S],s.y,s.z)):M===1?(u.up.set(0,0,l[S]),u.position.set(s.x,s.y,s.z),u.lookAt(s.x,s.y+d[S],s.z)):(u.up.set(0,l[S],0),u.position.set(s.x,s.y,s.z),u.lookAt(s.x,s.y,s.z+d[S]));const C=this._cubeSize;Nr(r,M*C,S>2?C:0,C,C),h.setRenderTarget(r),c&&h.render(p,u),h.render(e,u)}p.geometry.dispose(),p.material.dispose(),h.toneMapping=m,h.autoClear=f,e.background=A}_textureToCubeUV(e,t){const n=this._renderer,r=e.mapping===Ii||e.mapping===Ni;r?(this._cubemapMaterial===null&&(this._cubemapMaterial=Ua()),this._cubemapMaterial.uniforms.flipEnvMap.value=e.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=La());const s=r?this._cubemapMaterial:this._equirectMaterial,o=new Ft(this._lodPlanes[0],s),a=s.uniforms;a.envMap.value=e;const u=this._cubeSize;Nr(t,0,0,3*u,2*u),n.setRenderTarget(t),n.render(o,ws)}_applyPMREM(e){const t=this._renderer,n=t.autoClear;t.autoClear=!1;const r=this._lodPlanes.length;for(let s=1;s<r;s++){const o=Math.sqrt(this._sigmas[s]*this._sigmas[s]-this._sigmas[s-1]*this._sigmas[s-1]),a=Ca[(r-s-1)%Ca.length];this._blur(e,s-1,s,o,a)}t.autoClear=n}_blur(e,t,n,r,s){const o=this._pingPongRenderTarget;this._halfBlur(e,o,t,n,r,"latitudinal",s),this._halfBlur(o,e,n,n,r,"longitudinal",s)}_halfBlur(e,t,n,r,s,o,a){const u=this._renderer,l=this._blurMaterial;o!=="latitudinal"&&o!=="longitudinal"&&console.error("blur direction must be either latitudinal or longitudinal!");const d=3,h=new Ft(this._lodPlanes[r],l),f=l.uniforms,m=this._sizeLods[n]-1,_=isFinite(s)?Math.PI/(2*m):2*Math.PI/(2*ei-1),v=s/_,p=isFinite(s)?1+Math.floor(d*v):ei;p>ei&&console.warn(`sigmaRadians, ${s}, is too large and will clip, as it requested ${p} samples when the maximum is set to ${ei}`);const c=[];let A=0;for(let P=0;P<ei;++P){const I=P/v,y=Math.exp(-I*I/2);c.push(y),P===0?A+=y:P<p&&(A+=2*y)}for(let P=0;P<c.length;P++)c[P]=c[P]/A;f.envMap.value=e.texture,f.samples.value=p,f.weights.value=c,f.latitudinal.value=o==="latitudinal",a&&(f.poleAxis.value=a);const{_lodMax:S}=this;f.dTheta.value=_,f.mipInt.value=S-n;const M=this._sizeLods[r],C=3*M*(r>S-wi?r-S+wi:0),R=4*(this._cubeSize-M);Nr(t,C,R,3*M,2*M),u.setRenderTarget(t),u.render(h,ws)}}function uf(i){const e=[],t=[],n=[];let r=i;const s=i-wi+1+wa.length;for(let o=0;o<s;o++){const a=Math.pow(2,r);t.push(a);let u=1/a;o>i-wi?u=wa[o-i+wi-1]:o===0&&(u=0),n.push(u);const l=1/(a-2),d=-l,h=1+l,f=[d,d,h,d,h,h,d,d,h,h,d,h],m=6,_=6,v=3,p=2,c=1,A=new Float32Array(v*_*m),S=new Float32Array(p*_*m),M=new Float32Array(c*_*m);for(let R=0;R<m;R++){const P=R%3*2/3-1,I=R>2?0:-1,y=[P,I,0,P+2/3,I,0,P+2/3,I+1,0,P,I,0,P+2/3,I+1,0,P,I+1,0];A.set(y,v*_*R),S.set(f,p*_*R);const E=[R,R,R,R,R,R];M.set(E,c*_*R)}const C=new yt;C.setAttribute("position",new Bt(A,v)),C.setAttribute("uv",new Bt(S,p)),C.setAttribute("faceIndex",new Bt(M,c)),e.push(C),r>wi&&r--}return{lodPlanes:e,sizeLods:t,sigmas:n}}function Da(i,e,t){const n=new ri(i,e,t);return n.texture.mapping=jr,n.texture.name="PMREM.cubeUv",n.scissorTest=!0,n}function Nr(i,e,t,n,r){i.viewport.set(e,t,n,r),i.scissor.set(e,t,n,r)}function hf(i,e,t){const n=new Float32Array(ei),r=new B(0,1,0);return new Gn({name:"SphericalGaussianBlur",defines:{n:ei,CUBEUV_TEXEL_WIDTH:1/e,CUBEUV_TEXEL_HEIGHT:1/t,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},samples:{value:1},weights:{value:n},latitudinal:{value:!1},dTheta:{value:0},mipInt:{value:0},poleAxis:{value:r}},vertexShader:Go(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform int samples;
			uniform float weights[ n ];
			uniform bool latitudinal;
			uniform float dTheta;
			uniform float mipInt;
			uniform vec3 poleAxis;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			vec3 getSample( float theta, vec3 axis ) {

				float cosTheta = cos( theta );
				// Rodrigues' axis-angle rotation
				vec3 sampleDirection = vOutputDirection * cosTheta
					+ cross( axis, vOutputDirection ) * sin( theta )
					+ axis * dot( axis, vOutputDirection ) * ( 1.0 - cosTheta );

				return bilinearCubeUV( envMap, sampleDirection, mipInt );

			}

			void main() {

				vec3 axis = latitudinal ? poleAxis : cross( poleAxis, vOutputDirection );

				if ( all( equal( axis, vec3( 0.0 ) ) ) ) {

					axis = vec3( vOutputDirection.z, 0.0, - vOutputDirection.x );

				}

				axis = normalize( axis );

				gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
				gl_FragColor.rgb += weights[ 0 ] * getSample( 0.0, axis );

				for ( int i = 1; i < n; i++ ) {

					if ( i >= samples ) {

						break;

					}

					float theta = dTheta * float( i );
					gl_FragColor.rgb += weights[ i ] * getSample( -1.0 * theta, axis );
					gl_FragColor.rgb += weights[ i ] * getSample( theta, axis );

				}

			}
		`,blending:Hn,depthTest:!1,depthWrite:!1})}function La(){return new Gn({name:"EquirectangularToCubeUV",uniforms:{envMap:{value:null}},vertexShader:Go(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;

			#include <common>

			void main() {

				vec3 outputDirection = normalize( vOutputDirection );
				vec2 uv = equirectUv( outputDirection );

				gl_FragColor = vec4( texture2D ( envMap, uv ).rgb, 1.0 );

			}
		`,blending:Hn,depthTest:!1,depthWrite:!1})}function Ua(){return new Gn({name:"CubemapToCubeUV",uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:Go(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:Hn,depthTest:!1,depthWrite:!1})}function Go(){return`

		precision mediump float;
		precision mediump int;

		attribute float faceIndex;

		varying vec3 vOutputDirection;

		// RH coordinate system; PMREM face-indexing convention
		vec3 getDirection( vec2 uv, float face ) {

			uv = 2.0 * uv - 1.0;

			vec3 direction = vec3( uv, 1.0 );

			if ( face == 0.0 ) {

				direction = direction.zyx; // ( 1, v, u ) pos x

			} else if ( face == 1.0 ) {

				direction = direction.xzy;
				direction.xz *= -1.0; // ( -u, 1, -v ) pos y

			} else if ( face == 2.0 ) {

				direction.x *= -1.0; // ( -u, v, 1 ) pos z

			} else if ( face == 3.0 ) {

				direction = direction.zyx;
				direction.xz *= -1.0; // ( -1, v, -u ) neg x

			} else if ( face == 4.0 ) {

				direction = direction.xzy;
				direction.xy *= -1.0; // ( -u, -1, v ) neg y

			} else if ( face == 5.0 ) {

				direction.z *= -1.0; // ( u, v, -1 ) neg z

			}

			return direction;

		}

		void main() {

			vOutputDirection = getDirection( uv, faceIndex );
			gl_Position = vec4( position, 1.0 );

		}
	`}function df(i){let e=new WeakMap,t=null;function n(a){if(a&&a.isTexture){const u=a.mapping,l=u===Ys||u===js,d=u===Ii||u===Ni;if(l||d){let h=e.get(a);const f=h!==void 0?h.texture.pmremVersion:0;if(a.isRenderTargetTexture&&a.pmremVersion!==f)return t===null&&(t=new Pa(i)),h=l?t.fromEquirectangular(a,h):t.fromCubemap(a,h),h.texture.pmremVersion=a.pmremVersion,e.set(a,h),h.texture;if(h!==void 0)return h.texture;{const m=a.image;return l&&m&&m.height>0||d&&m&&r(m)?(t===null&&(t=new Pa(i)),h=l?t.fromEquirectangular(a):t.fromCubemap(a),h.texture.pmremVersion=a.pmremVersion,e.set(a,h),a.addEventListener("dispose",s),h.texture):null}}}return a}function r(a){let u=0;const l=6;for(let d=0;d<l;d++)a[d]!==void 0&&u++;return u===l}function s(a){const u=a.target;u.removeEventListener("dispose",s);const l=e.get(u);l!==void 0&&(e.delete(u),l.dispose())}function o(){e=new WeakMap,t!==null&&(t.dispose(),t=null)}return{get:n,dispose:o}}function ff(i){const e={};function t(n){if(e[n]!==void 0)return e[n];let r;switch(n){case"WEBGL_depth_texture":r=i.getExtension("WEBGL_depth_texture")||i.getExtension("MOZ_WEBGL_depth_texture")||i.getExtension("WEBKIT_WEBGL_depth_texture");break;case"EXT_texture_filter_anisotropic":r=i.getExtension("EXT_texture_filter_anisotropic")||i.getExtension("MOZ_EXT_texture_filter_anisotropic")||i.getExtension("WEBKIT_EXT_texture_filter_anisotropic");break;case"WEBGL_compressed_texture_s3tc":r=i.getExtension("WEBGL_compressed_texture_s3tc")||i.getExtension("MOZ_WEBGL_compressed_texture_s3tc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_s3tc");break;case"WEBGL_compressed_texture_pvrtc":r=i.getExtension("WEBGL_compressed_texture_pvrtc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_pvrtc");break;default:r=i.getExtension(n)}return e[n]=r,r}return{has:function(n){return t(n)!==null},init:function(){t("EXT_color_buffer_float"),t("WEBGL_clip_cull_distance"),t("OES_texture_float_linear"),t("EXT_color_buffer_half_float"),t("WEBGL_multisampled_render_to_texture"),t("WEBGL_render_shared_exponent")},get:function(n){const r=t(n);return r===null&&Di("THREE.WebGLRenderer: "+n+" extension not supported."),r}}}function pf(i,e,t,n){const r={},s=new WeakMap;function o(h){const f=h.target;f.index!==null&&e.remove(f.index);for(const _ in f.attributes)e.remove(f.attributes[_]);f.removeEventListener("dispose",o),delete r[f.id];const m=s.get(f);m&&(e.remove(m),s.delete(f)),n.releaseStatesOfGeometry(f),f.isInstancedBufferGeometry===!0&&delete f._maxInstanceCount,t.memory.geometries--}function a(h,f){return r[f.id]===!0||(f.addEventListener("dispose",o),r[f.id]=!0,t.memory.geometries++),f}function u(h){const f=h.attributes;for(const m in f)e.update(f[m],i.ARRAY_BUFFER)}function l(h){const f=[],m=h.index,_=h.attributes.position;let v=0;if(m!==null){const A=m.array;v=m.version;for(let S=0,M=A.length;S<M;S+=3){const C=A[S+0],R=A[S+1],P=A[S+2];f.push(C,R,R,P,P,C)}}else if(_!==void 0){const A=_.array;v=_.version;for(let S=0,M=A.length/3-1;S<M;S+=3){const C=S+0,R=S+1,P=S+2;f.push(C,R,R,P,P,C)}}else return;const p=new(fl(f)?_l:gl)(f,1);p.version=v;const c=s.get(h);c&&e.remove(c),s.set(h,p)}function d(h){const f=s.get(h);if(f){const m=h.index;m!==null&&f.version<m.version&&l(h)}else l(h);return s.get(h)}return{get:a,update:u,getWireframeAttribute:d}}function mf(i,e,t){let n;function r(f){n=f}let s,o;function a(f){s=f.type,o=f.bytesPerElement}function u(f,m){i.drawElements(n,m,s,f*o),t.update(m,n,1)}function l(f,m,_){_!==0&&(i.drawElementsInstanced(n,m,s,f*o,_),t.update(m,n,_))}function d(f,m,_){if(_===0)return;e.get("WEBGL_multi_draw").multiDrawElementsWEBGL(n,m,0,s,f,0,_);let p=0;for(let c=0;c<_;c++)p+=m[c];t.update(p,n,1)}function h(f,m,_,v){if(_===0)return;const p=e.get("WEBGL_multi_draw");if(p===null)for(let c=0;c<f.length;c++)l(f[c]/o,m[c],v[c]);else{p.multiDrawElementsInstancedWEBGL(n,m,0,s,f,0,v,0,_);let c=0;for(let A=0;A<_;A++)c+=m[A]*v[A];t.update(c,n,1)}}this.setMode=r,this.setIndex=a,this.render=u,this.renderInstances=l,this.renderMultiDraw=d,this.renderMultiDrawInstances=h}function gf(i){const e={geometries:0,textures:0},t={frame:0,calls:0,triangles:0,points:0,lines:0};function n(s,o,a){switch(t.calls++,o){case i.TRIANGLES:t.triangles+=a*(s/3);break;case i.LINES:t.lines+=a*(s/2);break;case i.LINE_STRIP:t.lines+=a*(s-1);break;case i.LINE_LOOP:t.lines+=a*s;break;case i.POINTS:t.points+=a*s;break;default:console.error("THREE.WebGLInfo: Unknown draw mode:",o);break}}function r(){t.calls=0,t.triangles=0,t.points=0,t.lines=0}return{memory:e,render:t,programs:null,autoReset:!0,reset:r,update:n}}function _f(i,e,t){const n=new WeakMap,r=new Mt;function s(o,a,u){const l=o.morphTargetInfluences,d=a.morphAttributes.position||a.morphAttributes.normal||a.morphAttributes.color,h=d!==void 0?d.length:0;let f=n.get(a);if(f===void 0||f.count!==h){let y=function(){P.dispose(),n.delete(a),a.removeEventListener("dispose",y)};f!==void 0&&f.texture.dispose();const m=a.morphAttributes.position!==void 0,_=a.morphAttributes.normal!==void 0,v=a.morphAttributes.color!==void 0,p=a.morphAttributes.position||[],c=a.morphAttributes.normal||[],A=a.morphAttributes.color||[];let S=0;m===!0&&(S=1),_===!0&&(S=2),v===!0&&(S=3);let M=a.attributes.position.count*S,C=1;M>e.maxTextureSize&&(C=Math.ceil(M/e.maxTextureSize),M=e.maxTextureSize);const R=new Float32Array(M*C*4*h),P=new pl(R,M,C,h);P.type=Cn,P.needsUpdate=!0;const I=S*4;for(let E=0;E<h;E++){const w=p[E],Q=c[E],j=A[E],Z=M*C*4*E;for(let re=0;re<w.count;re++){const X=re*I;m===!0&&(r.fromBufferAttribute(w,re),R[Z+X+0]=r.x,R[Z+X+1]=r.y,R[Z+X+2]=r.z,R[Z+X+3]=0),_===!0&&(r.fromBufferAttribute(Q,re),R[Z+X+4]=r.x,R[Z+X+5]=r.y,R[Z+X+6]=r.z,R[Z+X+7]=0),v===!0&&(r.fromBufferAttribute(j,re),R[Z+X+8]=r.x,R[Z+X+9]=r.y,R[Z+X+10]=r.z,R[Z+X+11]=j.itemSize===4?r.w:1)}}f={count:h,texture:P,size:new Ye(M,C)},n.set(a,f),a.addEventListener("dispose",y)}if(o.isInstancedMesh===!0&&o.morphTexture!==null)u.getUniforms().setValue(i,"morphTexture",o.morphTexture,t);else{let m=0;for(let v=0;v<l.length;v++)m+=l[v];const _=a.morphTargetsRelative?1:1-m;u.getUniforms().setValue(i,"morphTargetBaseInfluence",_),u.getUniforms().setValue(i,"morphTargetInfluences",l)}u.getUniforms().setValue(i,"morphTargetsTexture",f.texture,t),u.getUniforms().setValue(i,"morphTargetsTextureSize",f.size)}return{update:s}}function vf(i,e,t,n){let r=new WeakMap;function s(u){const l=n.render.frame,d=u.geometry,h=e.get(u,d);if(r.get(h)!==l&&(e.update(h),r.set(h,l)),u.isInstancedMesh&&(u.hasEventListener("dispose",a)===!1&&u.addEventListener("dispose",a),r.get(u)!==l&&(t.update(u.instanceMatrix,i.ARRAY_BUFFER),u.instanceColor!==null&&t.update(u.instanceColor,i.ARRAY_BUFFER),r.set(u,l))),u.isSkinnedMesh){const f=u.skeleton;r.get(f)!==l&&(f.update(),r.set(f,l))}return h}function o(){r=new WeakMap}function a(u){const l=u.target;l.removeEventListener("dispose",a),t.remove(l.instanceMatrix),l.instanceColor!==null&&t.remove(l.instanceColor)}return{update:s,dispose:o}}const wl=new Ot,Ia=new yl(1,1),Rl=new pl,Cl=new Nc,Pl=new Ml,Na=[],Fa=[],Oa=new Float32Array(16),Ba=new Float32Array(9),za=new Float32Array(4);function zi(i,e,t){const n=i[0];if(n<=0||n>0)return i;const r=e*t;let s=Na[r];if(s===void 0&&(s=new Float32Array(r),Na[r]=s),e!==0){n.toArray(s,0);for(let o=1,a=0;o!==e;++o)a+=t,i[o].toArray(s,a)}return s}function At(i,e){if(i.length!==e.length)return!1;for(let t=0,n=i.length;t<n;t++)if(i[t]!==e[t])return!1;return!0}function wt(i,e){for(let t=0,n=e.length;t<n;t++)i[t]=e[t]}function Jr(i,e){let t=Fa[e];t===void 0&&(t=new Int32Array(e),Fa[e]=t);for(let n=0;n!==e;++n)t[n]=i.allocateTextureUnit();return t}function xf(i,e){const t=this.cache;t[0]!==e&&(i.uniform1f(this.addr,e),t[0]=e)}function Mf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2f(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(At(t,e))return;i.uniform2fv(this.addr,e),wt(t,e)}}function Sf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3f(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else if(e.r!==void 0)(t[0]!==e.r||t[1]!==e.g||t[2]!==e.b)&&(i.uniform3f(this.addr,e.r,e.g,e.b),t[0]=e.r,t[1]=e.g,t[2]=e.b);else{if(At(t,e))return;i.uniform3fv(this.addr,e),wt(t,e)}}function yf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4f(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(At(t,e))return;i.uniform4fv(this.addr,e),wt(t,e)}}function Ef(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(At(t,e))return;i.uniformMatrix2fv(this.addr,!1,e),wt(t,e)}else{if(At(t,n))return;za.set(n),i.uniformMatrix2fv(this.addr,!1,za),wt(t,n)}}function Tf(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(At(t,e))return;i.uniformMatrix3fv(this.addr,!1,e),wt(t,e)}else{if(At(t,n))return;Ba.set(n),i.uniformMatrix3fv(this.addr,!1,Ba),wt(t,n)}}function bf(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(At(t,e))return;i.uniformMatrix4fv(this.addr,!1,e),wt(t,e)}else{if(At(t,n))return;Oa.set(n),i.uniformMatrix4fv(this.addr,!1,Oa),wt(t,n)}}function Af(i,e){const t=this.cache;t[0]!==e&&(i.uniform1i(this.addr,e),t[0]=e)}function wf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2i(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(At(t,e))return;i.uniform2iv(this.addr,e),wt(t,e)}}function Rf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3i(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(At(t,e))return;i.uniform3iv(this.addr,e),wt(t,e)}}function Cf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4i(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(At(t,e))return;i.uniform4iv(this.addr,e),wt(t,e)}}function Pf(i,e){const t=this.cache;t[0]!==e&&(i.uniform1ui(this.addr,e),t[0]=e)}function Df(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2ui(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(At(t,e))return;i.uniform2uiv(this.addr,e),wt(t,e)}}function Lf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3ui(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(At(t,e))return;i.uniform3uiv(this.addr,e),wt(t,e)}}function Uf(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4ui(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(At(t,e))return;i.uniform4uiv(this.addr,e),wt(t,e)}}function If(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r);let s;this.type===i.SAMPLER_2D_SHADOW?(Ia.compareFunction=dl,s=Ia):s=wl,t.setTexture2D(e||s,r)}function Nf(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTexture3D(e||Cl,r)}function Ff(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTextureCube(e||Pl,r)}function Of(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTexture2DArray(e||Rl,r)}function Bf(i){switch(i){case 5126:return xf;case 35664:return Mf;case 35665:return Sf;case 35666:return yf;case 35674:return Ef;case 35675:return Tf;case 35676:return bf;case 5124:case 35670:return Af;case 35667:case 35671:return wf;case 35668:case 35672:return Rf;case 35669:case 35673:return Cf;case 5125:return Pf;case 36294:return Df;case 36295:return Lf;case 36296:return Uf;case 35678:case 36198:case 36298:case 36306:case 35682:return If;case 35679:case 36299:case 36307:return Nf;case 35680:case 36300:case 36308:case 36293:return Ff;case 36289:case 36303:case 36311:case 36292:return Of}}function zf(i,e){i.uniform1fv(this.addr,e)}function Hf(i,e){const t=zi(e,this.size,2);i.uniform2fv(this.addr,t)}function kf(i,e){const t=zi(e,this.size,3);i.uniform3fv(this.addr,t)}function Vf(i,e){const t=zi(e,this.size,4);i.uniform4fv(this.addr,t)}function Gf(i,e){const t=zi(e,this.size,4);i.uniformMatrix2fv(this.addr,!1,t)}function Wf(i,e){const t=zi(e,this.size,9);i.uniformMatrix3fv(this.addr,!1,t)}function Xf(i,e){const t=zi(e,this.size,16);i.uniformMatrix4fv(this.addr,!1,t)}function qf(i,e){i.uniform1iv(this.addr,e)}function Yf(i,e){i.uniform2iv(this.addr,e)}function jf(i,e){i.uniform3iv(this.addr,e)}function Kf(i,e){i.uniform4iv(this.addr,e)}function Zf(i,e){i.uniform1uiv(this.addr,e)}function $f(i,e){i.uniform2uiv(this.addr,e)}function Jf(i,e){i.uniform3uiv(this.addr,e)}function Qf(i,e){i.uniform4uiv(this.addr,e)}function ep(i,e,t){const n=this.cache,r=e.length,s=Jr(t,r);At(n,s)||(i.uniform1iv(this.addr,s),wt(n,s));for(let o=0;o!==r;++o)t.setTexture2D(e[o]||wl,s[o])}function tp(i,e,t){const n=this.cache,r=e.length,s=Jr(t,r);At(n,s)||(i.uniform1iv(this.addr,s),wt(n,s));for(let o=0;o!==r;++o)t.setTexture3D(e[o]||Cl,s[o])}function np(i,e,t){const n=this.cache,r=e.length,s=Jr(t,r);At(n,s)||(i.uniform1iv(this.addr,s),wt(n,s));for(let o=0;o!==r;++o)t.setTextureCube(e[o]||Pl,s[o])}function ip(i,e,t){const n=this.cache,r=e.length,s=Jr(t,r);At(n,s)||(i.uniform1iv(this.addr,s),wt(n,s));for(let o=0;o!==r;++o)t.setTexture2DArray(e[o]||Rl,s[o])}function rp(i){switch(i){case 5126:return zf;case 35664:return Hf;case 35665:return kf;case 35666:return Vf;case 35674:return Gf;case 35675:return Wf;case 35676:return Xf;case 5124:case 35670:return qf;case 35667:case 35671:return Yf;case 35668:case 35672:return jf;case 35669:case 35673:return Kf;case 5125:return Zf;case 36294:return $f;case 36295:return Jf;case 36296:return Qf;case 35678:case 36198:case 36298:case 36306:case 35682:return ep;case 35679:case 36299:case 36307:return tp;case 35680:case 36300:case 36308:case 36293:return np;case 36289:case 36303:case 36311:case 36292:return ip}}class sp{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.setValue=Bf(t.type)}}class op{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.size=t.size,this.setValue=rp(t.type)}}class ap{constructor(e){this.id=e,this.seq=[],this.map={}}setValue(e,t,n){const r=this.seq;for(let s=0,o=r.length;s!==o;++s){const a=r[s];a.setValue(e,t[a.id],n)}}}const Ls=/(\w+)(\])?(\[|\.)?/g;function Ha(i,e){i.seq.push(e),i.map[e.id]=e}function lp(i,e,t){const n=i.name,r=n.length;for(Ls.lastIndex=0;;){const s=Ls.exec(n),o=Ls.lastIndex;let a=s[1];const u=s[2]==="]",l=s[3];if(u&&(a=a|0),l===void 0||l==="["&&o+2===r){Ha(t,l===void 0?new sp(a,i,e):new op(a,i,e));break}else{let h=t.map[a];h===void 0&&(h=new ap(a),Ha(t,h)),t=h}}}class Gr{constructor(e,t){this.seq=[],this.map={};const n=e.getProgramParameter(t,e.ACTIVE_UNIFORMS);for(let r=0;r<n;++r){const s=e.getActiveUniform(t,r),o=e.getUniformLocation(t,s.name);lp(s,o,this)}}setValue(e,t,n,r){const s=this.map[t];s!==void 0&&s.setValue(e,n,r)}setOptional(e,t,n){const r=t[n];r!==void 0&&this.setValue(e,n,r)}static upload(e,t,n,r){for(let s=0,o=t.length;s!==o;++s){const a=t[s],u=n[a.id];u.needsUpdate!==!1&&a.setValue(e,u.value,r)}}static seqWithValue(e,t){const n=[];for(let r=0,s=e.length;r!==s;++r){const o=e[r];o.id in t&&n.push(o)}return n}}function ka(i,e,t){const n=i.createShader(e);return i.shaderSource(n,t),i.compileShader(n),n}const cp=37297;let up=0;function hp(i,e){const t=i.split(`
`),n=[],r=Math.max(e-6,0),s=Math.min(e+6,t.length);for(let o=r;o<s;o++){const a=o+1;n.push(`${a===e?">":" "} ${a}: ${t[o]}`)}return n.join(`
`)}const Va=new Qe;function dp(i){at._getMatrix(Va,at.workingColorSpace,i);const e=`mat3( ${Va.elements.map(t=>t.toFixed(4))} )`;switch(at.getTransfer(i)){case Wr:return[e,"LinearTransferOETF"];case ht:return[e,"sRGBTransferOETF"];default:return console.warn("THREE.WebGLProgram: Unsupported color space: ",i),[e,"LinearTransferOETF"]}}function Ga(i,e,t){const n=i.getShaderParameter(e,i.COMPILE_STATUS),s=(i.getShaderInfoLog(e)||"").trim();if(n&&s==="")return"";const o=/ERROR: 0:(\d+)/.exec(s);if(o){const a=parseInt(o[1]);return t.toUpperCase()+`

`+s+`

`+hp(i.getShaderSource(e),a)}else return s}function fp(i,e){const t=dp(e);return[`vec4 ${i}( vec4 value ) {`,`	return ${t[1]}( vec4( value.rgb * ${t[0]}, value.a ) );`,"}"].join(`
`)}function pp(i,e){let t;switch(e){case lc:t="Linear";break;case cc:t="Reinhard";break;case uc:t="Cineon";break;case hc:t="ACESFilmic";break;case fc:t="AgX";break;case pc:t="Neutral";break;case dc:t="Custom";break;default:console.warn("THREE.WebGLProgram: Unsupported toneMapping:",e),t="Linear"}return"vec3 "+i+"( vec3 color ) { return "+t+"ToneMapping( color ); }"}const Fr=new B;function mp(){at.getLuminanceCoefficients(Fr);const i=Fr.x.toFixed(4),e=Fr.y.toFixed(4),t=Fr.z.toFixed(4);return["float luminance( const in vec3 rgb ) {",`	const vec3 weights = vec3( ${i}, ${e}, ${t} );`,"	return dot( weights, rgb );","}"].join(`
`)}function gp(i){return[i.extensionClipCullDistance?"#extension GL_ANGLE_clip_cull_distance : require":"",i.extensionMultiDraw?"#extension GL_ANGLE_multi_draw : require":""].filter(Ki).join(`
`)}function _p(i){const e=[];for(const t in i){const n=i[t];n!==!1&&e.push("#define "+t+" "+n)}return e.join(`
`)}function vp(i,e){const t={},n=i.getProgramParameter(e,i.ACTIVE_ATTRIBUTES);for(let r=0;r<n;r++){const s=i.getActiveAttrib(e,r),o=s.name;let a=1;s.type===i.FLOAT_MAT2&&(a=2),s.type===i.FLOAT_MAT3&&(a=3),s.type===i.FLOAT_MAT4&&(a=4),t[o]={type:s.type,location:i.getAttribLocation(e,o),locationSize:a}}return t}function Ki(i){return i!==""}function Wa(i,e){const t=e.numSpotLightShadows+e.numSpotLightMaps-e.numSpotLightShadowsWithMaps;return i.replace(/NUM_DIR_LIGHTS/g,e.numDirLights).replace(/NUM_SPOT_LIGHTS/g,e.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,e.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,t).replace(/NUM_RECT_AREA_LIGHTS/g,e.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,e.numPointLights).replace(/NUM_HEMI_LIGHTS/g,e.numHemiLights).replace(/NUM_DIR_LIGHT_SHADOWS/g,e.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,e.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,e.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,e.numPointLightShadows)}function Xa(i,e){return i.replace(/NUM_CLIPPING_PLANES/g,e.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,e.numClippingPlanes-e.numClipIntersection)}const xp=/^[ \t]*#include +<([\w\d./]+)>/gm;function To(i){return i.replace(xp,Sp)}const Mp=new Map;function Sp(i,e){let t=et[e];if(t===void 0){const n=Mp.get(e);if(n!==void 0)t=et[n],console.warn('THREE.WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.',e,n);else throw new Error("Can not resolve #include <"+e+">")}return To(t)}const yp=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function qa(i){return i.replace(yp,Ep)}function Ep(i,e,t,n){let r="";for(let s=parseInt(e);s<parseInt(t);s++)r+=n.replace(/\[\s*i\s*\]/g,"[ "+s+" ]").replace(/UNROLLED_LOOP_INDEX/g,s);return r}function Ya(i){let e=`precision ${i.precision} float;
	precision ${i.precision} int;
	precision ${i.precision} sampler2D;
	precision ${i.precision} samplerCube;
	precision ${i.precision} sampler3D;
	precision ${i.precision} sampler2DArray;
	precision ${i.precision} sampler2DShadow;
	precision ${i.precision} samplerCubeShadow;
	precision ${i.precision} sampler2DArrayShadow;
	precision ${i.precision} isampler2D;
	precision ${i.precision} isampler3D;
	precision ${i.precision} isamplerCube;
	precision ${i.precision} isampler2DArray;
	precision ${i.precision} usampler2D;
	precision ${i.precision} usampler3D;
	precision ${i.precision} usamplerCube;
	precision ${i.precision} usampler2DArray;
	`;return i.precision==="highp"?e+=`
#define HIGH_PRECISION`:i.precision==="mediump"?e+=`
#define MEDIUM_PRECISION`:i.precision==="lowp"&&(e+=`
#define LOW_PRECISION`),e}function Tp(i){let e="SHADOWMAP_TYPE_BASIC";return i.shadowMapType===nl?e="SHADOWMAP_TYPE_PCF":i.shadowMapType===kl?e="SHADOWMAP_TYPE_PCF_SOFT":i.shadowMapType===Tn&&(e="SHADOWMAP_TYPE_VSM"),e}function bp(i){let e="ENVMAP_TYPE_CUBE";if(i.envMap)switch(i.envMapMode){case Ii:case Ni:e="ENVMAP_TYPE_CUBE";break;case jr:e="ENVMAP_TYPE_CUBE_UV";break}return e}function Ap(i){let e="ENVMAP_MODE_REFLECTION";if(i.envMap)switch(i.envMapMode){case Ni:e="ENVMAP_MODE_REFRACTION";break}return e}function wp(i){let e="ENVMAP_BLENDING_NONE";if(i.envMap)switch(i.combine){case Ro:e="ENVMAP_BLENDING_MULTIPLY";break;case oc:e="ENVMAP_BLENDING_MIX";break;case ac:e="ENVMAP_BLENDING_ADD";break}return e}function Rp(i){const e=i.envMapCubeUVHeight;if(e===null)return null;const t=Math.log2(e)-2,n=1/e;return{texelWidth:1/(3*Math.max(Math.pow(2,t),112)),texelHeight:n,maxMip:t}}function Cp(i,e,t,n){const r=i.getContext(),s=t.defines;let o=t.vertexShader,a=t.fragmentShader;const u=Tp(t),l=bp(t),d=Ap(t),h=wp(t),f=Rp(t),m=gp(t),_=_p(s),v=r.createProgram();let p,c,A=t.glslVersion?"#version "+t.glslVersion+`
`:"";t.isRawShaderMaterial?(p=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_].filter(Ki).join(`
`),p.length>0&&(p+=`
`),c=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_].filter(Ki).join(`
`),c.length>0&&(c+=`
`)):(p=[Ya(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_,t.extensionClipCullDistance?"#define USE_CLIP_DISTANCE":"",t.batching?"#define USE_BATCHING":"",t.batchingColor?"#define USE_BATCHING_COLOR":"",t.instancing?"#define USE_INSTANCING":"",t.instancingColor?"#define USE_INSTANCING_COLOR":"",t.instancingMorph?"#define USE_INSTANCING_MORPH":"",t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.map?"#define USE_MAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+d:"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.displacementMap?"#define USE_DISPLACEMENTMAP":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.mapUv?"#define MAP_UV "+t.mapUv:"",t.alphaMapUv?"#define ALPHAMAP_UV "+t.alphaMapUv:"",t.lightMapUv?"#define LIGHTMAP_UV "+t.lightMapUv:"",t.aoMapUv?"#define AOMAP_UV "+t.aoMapUv:"",t.emissiveMapUv?"#define EMISSIVEMAP_UV "+t.emissiveMapUv:"",t.bumpMapUv?"#define BUMPMAP_UV "+t.bumpMapUv:"",t.normalMapUv?"#define NORMALMAP_UV "+t.normalMapUv:"",t.displacementMapUv?"#define DISPLACEMENTMAP_UV "+t.displacementMapUv:"",t.metalnessMapUv?"#define METALNESSMAP_UV "+t.metalnessMapUv:"",t.roughnessMapUv?"#define ROUGHNESSMAP_UV "+t.roughnessMapUv:"",t.anisotropyMapUv?"#define ANISOTROPYMAP_UV "+t.anisotropyMapUv:"",t.clearcoatMapUv?"#define CLEARCOATMAP_UV "+t.clearcoatMapUv:"",t.clearcoatNormalMapUv?"#define CLEARCOAT_NORMALMAP_UV "+t.clearcoatNormalMapUv:"",t.clearcoatRoughnessMapUv?"#define CLEARCOAT_ROUGHNESSMAP_UV "+t.clearcoatRoughnessMapUv:"",t.iridescenceMapUv?"#define IRIDESCENCEMAP_UV "+t.iridescenceMapUv:"",t.iridescenceThicknessMapUv?"#define IRIDESCENCE_THICKNESSMAP_UV "+t.iridescenceThicknessMapUv:"",t.sheenColorMapUv?"#define SHEEN_COLORMAP_UV "+t.sheenColorMapUv:"",t.sheenRoughnessMapUv?"#define SHEEN_ROUGHNESSMAP_UV "+t.sheenRoughnessMapUv:"",t.specularMapUv?"#define SPECULARMAP_UV "+t.specularMapUv:"",t.specularColorMapUv?"#define SPECULAR_COLORMAP_UV "+t.specularColorMapUv:"",t.specularIntensityMapUv?"#define SPECULAR_INTENSITYMAP_UV "+t.specularIntensityMapUv:"",t.transmissionMapUv?"#define TRANSMISSIONMAP_UV "+t.transmissionMapUv:"",t.thicknessMapUv?"#define THICKNESSMAP_UV "+t.thicknessMapUv:"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.flatShading?"#define FLAT_SHADED":"",t.skinning?"#define USE_SKINNING":"",t.morphTargets?"#define USE_MORPHTARGETS":"",t.morphNormals&&t.flatShading===!1?"#define USE_MORPHNORMALS":"",t.morphColors?"#define USE_MORPHCOLORS":"",t.morphTargetsCount>0?"#define MORPHTARGETS_TEXTURE_STRIDE "+t.morphTextureStride:"",t.morphTargetsCount>0?"#define MORPHTARGETS_COUNT "+t.morphTargetsCount:"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+u:"",t.sizeAttenuation?"#define USE_SIZEATTENUATION":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reversedDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 modelMatrix;","uniform mat4 modelViewMatrix;","uniform mat4 projectionMatrix;","uniform mat4 viewMatrix;","uniform mat3 normalMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;","#ifdef USE_INSTANCING","	attribute mat4 instanceMatrix;","#endif","#ifdef USE_INSTANCING_COLOR","	attribute vec3 instanceColor;","#endif","#ifdef USE_INSTANCING_MORPH","	uniform sampler2D morphTexture;","#endif","attribute vec3 position;","attribute vec3 normal;","attribute vec2 uv;","#ifdef USE_UV1","	attribute vec2 uv1;","#endif","#ifdef USE_UV2","	attribute vec2 uv2;","#endif","#ifdef USE_UV3","	attribute vec2 uv3;","#endif","#ifdef USE_TANGENT","	attribute vec4 tangent;","#endif","#if defined( USE_COLOR_ALPHA )","	attribute vec4 color;","#elif defined( USE_COLOR )","	attribute vec3 color;","#endif","#ifdef USE_SKINNING","	attribute vec4 skinIndex;","	attribute vec4 skinWeight;","#endif",`
`].filter(Ki).join(`
`),c=[Ya(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_,t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.alphaToCoverage?"#define ALPHA_TO_COVERAGE":"",t.map?"#define USE_MAP":"",t.matcap?"#define USE_MATCAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+l:"",t.envMap?"#define "+d:"",t.envMap?"#define "+h:"",f?"#define CUBEUV_TEXEL_WIDTH "+f.texelWidth:"",f?"#define CUBEUV_TEXEL_HEIGHT "+f.texelHeight:"",f?"#define CUBEUV_MAX_MIP "+f.maxMip+".0":"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoat?"#define USE_CLEARCOAT":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.dispersion?"#define USE_DISPERSION":"",t.iridescence?"#define USE_IRIDESCENCE":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaTest?"#define USE_ALPHATEST":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.sheen?"#define USE_SHEEN":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors||t.instancingColor||t.batchingColor?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.gradientMap?"#define USE_GRADIENTMAP":"",t.flatShading?"#define FLAT_SHADED":"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+u:"",t.premultipliedAlpha?"#define PREMULTIPLIED_ALPHA":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.decodeVideoTexture?"#define DECODE_VIDEO_TEXTURE":"",t.decodeVideoTextureEmissive?"#define DECODE_VIDEO_TEXTURE_EMISSIVE":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reversedDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 viewMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;",t.toneMapping!==kn?"#define TONE_MAPPING":"",t.toneMapping!==kn?et.tonemapping_pars_fragment:"",t.toneMapping!==kn?pp("toneMapping",t.toneMapping):"",t.dithering?"#define DITHERING":"",t.opaque?"#define OPAQUE":"",et.colorspace_pars_fragment,fp("linearToOutputTexel",t.outputColorSpace),mp(),t.useDepthPacking?"#define DEPTH_PACKING "+t.depthPacking:"",`
`].filter(Ki).join(`
`)),o=To(o),o=Wa(o,t),o=Xa(o,t),a=To(a),a=Wa(a,t),a=Xa(a,t),o=qa(o),a=qa(a),t.isRawShaderMaterial!==!0&&(A=`#version 300 es
`,p=[m,"#define attribute in","#define varying out","#define texture2D texture"].join(`
`)+`
`+p,c=["#define varying in",t.glslVersion===Jo?"":"layout(location = 0) out highp vec4 pc_fragColor;",t.glslVersion===Jo?"":"#define gl_FragColor pc_fragColor","#define gl_FragDepthEXT gl_FragDepth","#define texture2D texture","#define textureCube texture","#define texture2DProj textureProj","#define texture2DLodEXT textureLod","#define texture2DProjLodEXT textureProjLod","#define textureCubeLodEXT textureLod","#define texture2DGradEXT textureGrad","#define texture2DProjGradEXT textureProjGrad","#define textureCubeGradEXT textureGrad"].join(`
`)+`
`+c);const S=A+p+o,M=A+c+a,C=ka(r,r.VERTEX_SHADER,S),R=ka(r,r.FRAGMENT_SHADER,M);r.attachShader(v,C),r.attachShader(v,R),t.index0AttributeName!==void 0?r.bindAttribLocation(v,0,t.index0AttributeName):t.morphTargets===!0&&r.bindAttribLocation(v,0,"position"),r.linkProgram(v);function P(w){if(i.debug.checkShaderErrors){const Q=r.getProgramInfoLog(v)||"",j=r.getShaderInfoLog(C)||"",Z=r.getShaderInfoLog(R)||"",re=Q.trim(),X=j.trim(),ae=Z.trim();let W=!0,he=!0;if(r.getProgramParameter(v,r.LINK_STATUS)===!1)if(W=!1,typeof i.debug.onShaderError=="function")i.debug.onShaderError(r,v,C,R);else{const ye=Ga(r,C,"vertex"),Te=Ga(r,R,"fragment");console.error("THREE.WebGLProgram: Shader Error "+r.getError()+" - VALIDATE_STATUS "+r.getProgramParameter(v,r.VALIDATE_STATUS)+`

Material Name: `+w.name+`
Material Type: `+w.type+`

Program Info Log: `+re+`
`+ye+`
`+Te)}else re!==""?console.warn("THREE.WebGLProgram: Program Info Log:",re):(X===""||ae==="")&&(he=!1);he&&(w.diagnostics={runnable:W,programLog:re,vertexShader:{log:X,prefix:p},fragmentShader:{log:ae,prefix:c}})}r.deleteShader(C),r.deleteShader(R),I=new Gr(r,v),y=vp(r,v)}let I;this.getUniforms=function(){return I===void 0&&P(this),I};let y;this.getAttributes=function(){return y===void 0&&P(this),y};let E=t.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return E===!1&&(E=r.getProgramParameter(v,cp)),E},this.destroy=function(){n.releaseStatesOfProgram(this),r.deleteProgram(v),this.program=void 0},this.type=t.shaderType,this.name=t.shaderName,this.id=up++,this.cacheKey=e,this.usedTimes=1,this.program=v,this.vertexShader=C,this.fragmentShader=R,this}let Pp=0;class Dp{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(e){const t=e.vertexShader,n=e.fragmentShader,r=this._getShaderStage(t),s=this._getShaderStage(n),o=this._getShaderCacheForMaterial(e);return o.has(r)===!1&&(o.add(r),r.usedTimes++),o.has(s)===!1&&(o.add(s),s.usedTimes++),this}remove(e){const t=this.materialCache.get(e);for(const n of t)n.usedTimes--,n.usedTimes===0&&this.shaderCache.delete(n.code);return this.materialCache.delete(e),this}getVertexShaderID(e){return this._getShaderStage(e.vertexShader).id}getFragmentShaderID(e){return this._getShaderStage(e.fragmentShader).id}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(e){const t=this.materialCache;let n=t.get(e);return n===void 0&&(n=new Set,t.set(e,n)),n}_getShaderStage(e){const t=this.shaderCache;let n=t.get(e);return n===void 0&&(n=new Lp(e),t.set(e,n)),n}}class Lp{constructor(e){this.id=Pp++,this.code=e,this.usedTimes=0}}function Up(i,e,t,n,r,s,o){const a=new Oo,u=new Dp,l=new Set,d=[],h=r.logarithmicDepthBuffer,f=r.vertexTextures;let m=r.precision;const _={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distanceRGBA",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function v(y){return l.add(y),y===0?"uv":`uv${y}`}function p(y,E,w,Q,j){const Z=Q.fog,re=j.geometry,X=y.isMeshStandardMaterial?Q.environment:null,ae=(y.isMeshStandardMaterial?t:e).get(y.envMap||X),W=ae&&ae.mapping===jr?ae.image.height:null,he=_[y.type];y.precision!==null&&(m=r.getMaxPrecision(y.precision),m!==y.precision&&console.warn("THREE.WebGLProgram.getParameters:",y.precision,"not supported, using",m,"instead."));const ye=re.morphAttributes.position||re.morphAttributes.normal||re.morphAttributes.color,Te=ye!==void 0?ye.length:0;let ze=0;re.morphAttributes.position!==void 0&&(ze=1),re.morphAttributes.normal!==void 0&&(ze=2),re.morphAttributes.color!==void 0&&(ze=3);let nt,it,J,L;if(he){const Xe=pn[he];nt=Xe.vertexShader,it=Xe.fragmentShader}else nt=y.vertexShader,it=y.fragmentShader,u.update(y),J=u.getVertexShaderID(y),L=u.getFragmentShaderID(y);const D=i.getRenderTarget(),z=i.state.buffers.depth.getReversed(),H=j.isInstancedMesh===!0,G=j.isBatchedMesh===!0,Y=!!y.map,ee=!!y.matcap,b=!!ae,ne=!!y.aoMap,q=!!y.lightMap,me=!!y.bumpMap,K=!!y.normalMap,Ke=!!y.displacementMap,ue=!!y.emissiveMap,Ce=!!y.metalnessMap,$e=!!y.roughnessMap,Pe=y.anisotropy>0,T=y.clearcoat>0,g=y.dispersion>0,O=y.iridescence>0,te=y.sheen>0,se=y.transmission>0,$=Pe&&!!y.anisotropyMap,ve=T&&!!y.clearcoatMap,pe=T&&!!y.clearcoatNormalMap,we=T&&!!y.clearcoatRoughnessMap,Ue=O&&!!y.iridescenceMap,de=O&&!!y.iridescenceThicknessMap,xe=te&&!!y.sheenColorMap,Ne=te&&!!y.sheenRoughnessMap,De=!!y.specularMap,Me=!!y.specularColorMap,We=!!y.specularIntensityMap,U=se&&!!y.transmissionMap,fe=se&&!!y.thicknessMap,ge=!!y.gradientMap,be=!!y.alphaMap,ce=y.alphaTest>0,ie=!!y.alphaHash,Le=!!y.extensions;let Ve=kn;y.toneMapped&&(D===null||D.isXRRenderTarget===!0)&&(Ve=i.toneMapping);const tt={shaderID:he,shaderType:y.type,shaderName:y.name,vertexShader:nt,fragmentShader:it,defines:y.defines,customVertexShaderID:J,customFragmentShaderID:L,isRawShaderMaterial:y.isRawShaderMaterial===!0,glslVersion:y.glslVersion,precision:m,batching:G,batchingColor:G&&j._colorsTexture!==null,instancing:H,instancingColor:H&&j.instanceColor!==null,instancingMorph:H&&j.morphTexture!==null,supportsVertexTextures:f,outputColorSpace:D===null?i.outputColorSpace:D.isXRRenderTarget===!0?D.texture.colorSpace:Fi,alphaToCoverage:!!y.alphaToCoverage,map:Y,matcap:ee,envMap:b,envMapMode:b&&ae.mapping,envMapCubeUVHeight:W,aoMap:ne,lightMap:q,bumpMap:me,normalMap:K,displacementMap:f&&Ke,emissiveMap:ue,normalMapObjectSpace:K&&y.normalMapType===vc,normalMapTangentSpace:K&&y.normalMapType===No,metalnessMap:Ce,roughnessMap:$e,anisotropy:Pe,anisotropyMap:$,clearcoat:T,clearcoatMap:ve,clearcoatNormalMap:pe,clearcoatRoughnessMap:we,dispersion:g,iridescence:O,iridescenceMap:Ue,iridescenceThicknessMap:de,sheen:te,sheenColorMap:xe,sheenRoughnessMap:Ne,specularMap:De,specularColorMap:Me,specularIntensityMap:We,transmission:se,transmissionMap:U,thicknessMap:fe,gradientMap:ge,opaque:y.transparent===!1&&y.blending===Pi&&y.alphaToCoverage===!1,alphaMap:be,alphaTest:ce,alphaHash:ie,combine:y.combine,mapUv:Y&&v(y.map.channel),aoMapUv:ne&&v(y.aoMap.channel),lightMapUv:q&&v(y.lightMap.channel),bumpMapUv:me&&v(y.bumpMap.channel),normalMapUv:K&&v(y.normalMap.channel),displacementMapUv:Ke&&v(y.displacementMap.channel),emissiveMapUv:ue&&v(y.emissiveMap.channel),metalnessMapUv:Ce&&v(y.metalnessMap.channel),roughnessMapUv:$e&&v(y.roughnessMap.channel),anisotropyMapUv:$&&v(y.anisotropyMap.channel),clearcoatMapUv:ve&&v(y.clearcoatMap.channel),clearcoatNormalMapUv:pe&&v(y.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:we&&v(y.clearcoatRoughnessMap.channel),iridescenceMapUv:Ue&&v(y.iridescenceMap.channel),iridescenceThicknessMapUv:de&&v(y.iridescenceThicknessMap.channel),sheenColorMapUv:xe&&v(y.sheenColorMap.channel),sheenRoughnessMapUv:Ne&&v(y.sheenRoughnessMap.channel),specularMapUv:De&&v(y.specularMap.channel),specularColorMapUv:Me&&v(y.specularColorMap.channel),specularIntensityMapUv:We&&v(y.specularIntensityMap.channel),transmissionMapUv:U&&v(y.transmissionMap.channel),thicknessMapUv:fe&&v(y.thicknessMap.channel),alphaMapUv:be&&v(y.alphaMap.channel),vertexTangents:!!re.attributes.tangent&&(K||Pe),vertexColors:y.vertexColors,vertexAlphas:y.vertexColors===!0&&!!re.attributes.color&&re.attributes.color.itemSize===4,pointsUvs:j.isPoints===!0&&!!re.attributes.uv&&(Y||be),fog:!!Z,useFog:y.fog===!0,fogExp2:!!Z&&Z.isFogExp2,flatShading:y.flatShading===!0&&y.wireframe===!1,sizeAttenuation:y.sizeAttenuation===!0,logarithmicDepthBuffer:h,reversedDepthBuffer:z,skinning:j.isSkinnedMesh===!0,morphTargets:re.morphAttributes.position!==void 0,morphNormals:re.morphAttributes.normal!==void 0,morphColors:re.morphAttributes.color!==void 0,morphTargetsCount:Te,morphTextureStride:ze,numDirLights:E.directional.length,numPointLights:E.point.length,numSpotLights:E.spot.length,numSpotLightMaps:E.spotLightMap.length,numRectAreaLights:E.rectArea.length,numHemiLights:E.hemi.length,numDirLightShadows:E.directionalShadowMap.length,numPointLightShadows:E.pointShadowMap.length,numSpotLightShadows:E.spotShadowMap.length,numSpotLightShadowsWithMaps:E.numSpotLightShadowsWithMaps,numLightProbes:E.numLightProbes,numClippingPlanes:o.numPlanes,numClipIntersection:o.numIntersection,dithering:y.dithering,shadowMapEnabled:i.shadowMap.enabled&&w.length>0,shadowMapType:i.shadowMap.type,toneMapping:Ve,decodeVideoTexture:Y&&y.map.isVideoTexture===!0&&at.getTransfer(y.map.colorSpace)===ht,decodeVideoTextureEmissive:ue&&y.emissiveMap.isVideoTexture===!0&&at.getTransfer(y.emissiveMap.colorSpace)===ht,premultipliedAlpha:y.premultipliedAlpha,doubleSided:y.side===An,flipSided:y.side===Wt,useDepthPacking:y.depthPacking>=0,depthPacking:y.depthPacking||0,index0AttributeName:y.index0AttributeName,extensionClipCullDistance:Le&&y.extensions.clipCullDistance===!0&&n.has("WEBGL_clip_cull_distance"),extensionMultiDraw:(Le&&y.extensions.multiDraw===!0||G)&&n.has("WEBGL_multi_draw"),rendererExtensionParallelShaderCompile:n.has("KHR_parallel_shader_compile"),customProgramCacheKey:y.customProgramCacheKey()};return tt.vertexUv1s=l.has(1),tt.vertexUv2s=l.has(2),tt.vertexUv3s=l.has(3),l.clear(),tt}function c(y){const E=[];if(y.shaderID?E.push(y.shaderID):(E.push(y.customVertexShaderID),E.push(y.customFragmentShaderID)),y.defines!==void 0)for(const w in y.defines)E.push(w),E.push(y.defines[w]);return y.isRawShaderMaterial===!1&&(A(E,y),S(E,y),E.push(i.outputColorSpace)),E.push(y.customProgramCacheKey),E.join()}function A(y,E){y.push(E.precision),y.push(E.outputColorSpace),y.push(E.envMapMode),y.push(E.envMapCubeUVHeight),y.push(E.mapUv),y.push(E.alphaMapUv),y.push(E.lightMapUv),y.push(E.aoMapUv),y.push(E.bumpMapUv),y.push(E.normalMapUv),y.push(E.displacementMapUv),y.push(E.emissiveMapUv),y.push(E.metalnessMapUv),y.push(E.roughnessMapUv),y.push(E.anisotropyMapUv),y.push(E.clearcoatMapUv),y.push(E.clearcoatNormalMapUv),y.push(E.clearcoatRoughnessMapUv),y.push(E.iridescenceMapUv),y.push(E.iridescenceThicknessMapUv),y.push(E.sheenColorMapUv),y.push(E.sheenRoughnessMapUv),y.push(E.specularMapUv),y.push(E.specularColorMapUv),y.push(E.specularIntensityMapUv),y.push(E.transmissionMapUv),y.push(E.thicknessMapUv),y.push(E.combine),y.push(E.fogExp2),y.push(E.sizeAttenuation),y.push(E.morphTargetsCount),y.push(E.morphAttributeCount),y.push(E.numDirLights),y.push(E.numPointLights),y.push(E.numSpotLights),y.push(E.numSpotLightMaps),y.push(E.numHemiLights),y.push(E.numRectAreaLights),y.push(E.numDirLightShadows),y.push(E.numPointLightShadows),y.push(E.numSpotLightShadows),y.push(E.numSpotLightShadowsWithMaps),y.push(E.numLightProbes),y.push(E.shadowMapType),y.push(E.toneMapping),y.push(E.numClippingPlanes),y.push(E.numClipIntersection),y.push(E.depthPacking)}function S(y,E){a.disableAll(),E.supportsVertexTextures&&a.enable(0),E.instancing&&a.enable(1),E.instancingColor&&a.enable(2),E.instancingMorph&&a.enable(3),E.matcap&&a.enable(4),E.envMap&&a.enable(5),E.normalMapObjectSpace&&a.enable(6),E.normalMapTangentSpace&&a.enable(7),E.clearcoat&&a.enable(8),E.iridescence&&a.enable(9),E.alphaTest&&a.enable(10),E.vertexColors&&a.enable(11),E.vertexAlphas&&a.enable(12),E.vertexUv1s&&a.enable(13),E.vertexUv2s&&a.enable(14),E.vertexUv3s&&a.enable(15),E.vertexTangents&&a.enable(16),E.anisotropy&&a.enable(17),E.alphaHash&&a.enable(18),E.batching&&a.enable(19),E.dispersion&&a.enable(20),E.batchingColor&&a.enable(21),E.gradientMap&&a.enable(22),y.push(a.mask),a.disableAll(),E.fog&&a.enable(0),E.useFog&&a.enable(1),E.flatShading&&a.enable(2),E.logarithmicDepthBuffer&&a.enable(3),E.reversedDepthBuffer&&a.enable(4),E.skinning&&a.enable(5),E.morphTargets&&a.enable(6),E.morphNormals&&a.enable(7),E.morphColors&&a.enable(8),E.premultipliedAlpha&&a.enable(9),E.shadowMapEnabled&&a.enable(10),E.doubleSided&&a.enable(11),E.flipSided&&a.enable(12),E.useDepthPacking&&a.enable(13),E.dithering&&a.enable(14),E.transmission&&a.enable(15),E.sheen&&a.enable(16),E.opaque&&a.enable(17),E.pointsUvs&&a.enable(18),E.decodeVideoTexture&&a.enable(19),E.decodeVideoTextureEmissive&&a.enable(20),E.alphaToCoverage&&a.enable(21),y.push(a.mask)}function M(y){const E=_[y.type];let w;if(E){const Q=pn[E];w=jc.clone(Q.uniforms)}else w=y.uniforms;return w}function C(y,E){let w;for(let Q=0,j=d.length;Q<j;Q++){const Z=d[Q];if(Z.cacheKey===E){w=Z,++w.usedTimes;break}}return w===void 0&&(w=new Cp(i,E,y,s),d.push(w)),w}function R(y){if(--y.usedTimes===0){const E=d.indexOf(y);d[E]=d[d.length-1],d.pop(),y.destroy()}}function P(y){u.remove(y)}function I(){u.dispose()}return{getParameters:p,getProgramCacheKey:c,getUniforms:M,acquireProgram:C,releaseProgram:R,releaseShaderCache:P,programs:d,dispose:I}}function Ip(){let i=new WeakMap;function e(o){return i.has(o)}function t(o){let a=i.get(o);return a===void 0&&(a={},i.set(o,a)),a}function n(o){i.delete(o)}function r(o,a,u){i.get(o)[a]=u}function s(){i=new WeakMap}return{has:e,get:t,remove:n,update:r,dispose:s}}function Np(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.material.id!==e.material.id?i.material.id-e.material.id:i.z!==e.z?i.z-e.z:i.id-e.id}function ja(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.z!==e.z?e.z-i.z:i.id-e.id}function Ka(){const i=[];let e=0;const t=[],n=[],r=[];function s(){e=0,t.length=0,n.length=0,r.length=0}function o(h,f,m,_,v,p){let c=i[e];return c===void 0?(c={id:h.id,object:h,geometry:f,material:m,groupOrder:_,renderOrder:h.renderOrder,z:v,group:p},i[e]=c):(c.id=h.id,c.object=h,c.geometry=f,c.material=m,c.groupOrder=_,c.renderOrder=h.renderOrder,c.z=v,c.group=p),e++,c}function a(h,f,m,_,v,p){const c=o(h,f,m,_,v,p);m.transmission>0?n.push(c):m.transparent===!0?r.push(c):t.push(c)}function u(h,f,m,_,v,p){const c=o(h,f,m,_,v,p);m.transmission>0?n.unshift(c):m.transparent===!0?r.unshift(c):t.unshift(c)}function l(h,f){t.length>1&&t.sort(h||Np),n.length>1&&n.sort(f||ja),r.length>1&&r.sort(f||ja)}function d(){for(let h=e,f=i.length;h<f;h++){const m=i[h];if(m.id===null)break;m.id=null,m.object=null,m.geometry=null,m.material=null,m.group=null}}return{opaque:t,transmissive:n,transparent:r,init:s,push:a,unshift:u,finish:d,sort:l}}function Fp(){let i=new WeakMap;function e(n,r){const s=i.get(n);let o;return s===void 0?(o=new Ka,i.set(n,[o])):r>=s.length?(o=new Ka,s.push(o)):o=s[r],o}function t(){i=new WeakMap}return{get:e,dispose:t}}function Op(){const i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={direction:new B,color:new je};break;case"SpotLight":t={position:new B,direction:new B,color:new je,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case"PointLight":t={position:new B,color:new je,distance:0,decay:0};break;case"HemisphereLight":t={direction:new B,skyColor:new je,groundColor:new je};break;case"RectAreaLight":t={color:new je,position:new B,halfWidth:new B,halfHeight:new B};break}return i[e.id]=t,t}}}function Bp(){const i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Ye};break;case"SpotLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Ye};break;case"PointLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Ye,shadowCameraNear:1,shadowCameraFar:1e3};break}return i[e.id]=t,t}}}let zp=0;function Hp(i,e){return(e.castShadow?2:0)-(i.castShadow?2:0)+(e.map?1:0)-(i.map?1:0)}function kp(i){const e=new Op,t=Bp(),n={version:0,hash:{directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let l=0;l<9;l++)n.probe.push(new B);const r=new B,s=new gt,o=new gt;function a(l){let d=0,h=0,f=0;for(let y=0;y<9;y++)n.probe[y].set(0,0,0);let m=0,_=0,v=0,p=0,c=0,A=0,S=0,M=0,C=0,R=0,P=0;l.sort(Hp);for(let y=0,E=l.length;y<E;y++){const w=l[y],Q=w.color,j=w.intensity,Z=w.distance,re=w.shadow&&w.shadow.map?w.shadow.map.texture:null;if(w.isAmbientLight)d+=Q.r*j,h+=Q.g*j,f+=Q.b*j;else if(w.isLightProbe){for(let X=0;X<9;X++)n.probe[X].addScaledVector(w.sh.coefficients[X],j);P++}else if(w.isDirectionalLight){const X=e.get(w);if(X.color.copy(w.color).multiplyScalar(w.intensity),w.castShadow){const ae=w.shadow,W=t.get(w);W.shadowIntensity=ae.intensity,W.shadowBias=ae.bias,W.shadowNormalBias=ae.normalBias,W.shadowRadius=ae.radius,W.shadowMapSize=ae.mapSize,n.directionalShadow[m]=W,n.directionalShadowMap[m]=re,n.directionalShadowMatrix[m]=w.shadow.matrix,A++}n.directional[m]=X,m++}else if(w.isSpotLight){const X=e.get(w);X.position.setFromMatrixPosition(w.matrixWorld),X.color.copy(Q).multiplyScalar(j),X.distance=Z,X.coneCos=Math.cos(w.angle),X.penumbraCos=Math.cos(w.angle*(1-w.penumbra)),X.decay=w.decay,n.spot[v]=X;const ae=w.shadow;if(w.map&&(n.spotLightMap[C]=w.map,C++,ae.updateMatrices(w),w.castShadow&&R++),n.spotLightMatrix[v]=ae.matrix,w.castShadow){const W=t.get(w);W.shadowIntensity=ae.intensity,W.shadowBias=ae.bias,W.shadowNormalBias=ae.normalBias,W.shadowRadius=ae.radius,W.shadowMapSize=ae.mapSize,n.spotShadow[v]=W,n.spotShadowMap[v]=re,M++}v++}else if(w.isRectAreaLight){const X=e.get(w);X.color.copy(Q).multiplyScalar(j),X.halfWidth.set(w.width*.5,0,0),X.halfHeight.set(0,w.height*.5,0),n.rectArea[p]=X,p++}else if(w.isPointLight){const X=e.get(w);if(X.color.copy(w.color).multiplyScalar(w.intensity),X.distance=w.distance,X.decay=w.decay,w.castShadow){const ae=w.shadow,W=t.get(w);W.shadowIntensity=ae.intensity,W.shadowBias=ae.bias,W.shadowNormalBias=ae.normalBias,W.shadowRadius=ae.radius,W.shadowMapSize=ae.mapSize,W.shadowCameraNear=ae.camera.near,W.shadowCameraFar=ae.camera.far,n.pointShadow[_]=W,n.pointShadowMap[_]=re,n.pointShadowMatrix[_]=w.shadow.matrix,S++}n.point[_]=X,_++}else if(w.isHemisphereLight){const X=e.get(w);X.skyColor.copy(w.color).multiplyScalar(j),X.groundColor.copy(w.groundColor).multiplyScalar(j),n.hemi[c]=X,c++}}p>0&&(i.has("OES_texture_float_linear")===!0?(n.rectAreaLTC1=Se.LTC_FLOAT_1,n.rectAreaLTC2=Se.LTC_FLOAT_2):(n.rectAreaLTC1=Se.LTC_HALF_1,n.rectAreaLTC2=Se.LTC_HALF_2)),n.ambient[0]=d,n.ambient[1]=h,n.ambient[2]=f;const I=n.hash;(I.directionalLength!==m||I.pointLength!==_||I.spotLength!==v||I.rectAreaLength!==p||I.hemiLength!==c||I.numDirectionalShadows!==A||I.numPointShadows!==S||I.numSpotShadows!==M||I.numSpotMaps!==C||I.numLightProbes!==P)&&(n.directional.length=m,n.spot.length=v,n.rectArea.length=p,n.point.length=_,n.hemi.length=c,n.directionalShadow.length=A,n.directionalShadowMap.length=A,n.pointShadow.length=S,n.pointShadowMap.length=S,n.spotShadow.length=M,n.spotShadowMap.length=M,n.directionalShadowMatrix.length=A,n.pointShadowMatrix.length=S,n.spotLightMatrix.length=M+C-R,n.spotLightMap.length=C,n.numSpotLightShadowsWithMaps=R,n.numLightProbes=P,I.directionalLength=m,I.pointLength=_,I.spotLength=v,I.rectAreaLength=p,I.hemiLength=c,I.numDirectionalShadows=A,I.numPointShadows=S,I.numSpotShadows=M,I.numSpotMaps=C,I.numLightProbes=P,n.version=zp++)}function u(l,d){let h=0,f=0,m=0,_=0,v=0;const p=d.matrixWorldInverse;for(let c=0,A=l.length;c<A;c++){const S=l[c];if(S.isDirectionalLight){const M=n.directional[h];M.direction.setFromMatrixPosition(S.matrixWorld),r.setFromMatrixPosition(S.target.matrixWorld),M.direction.sub(r),M.direction.transformDirection(p),h++}else if(S.isSpotLight){const M=n.spot[m];M.position.setFromMatrixPosition(S.matrixWorld),M.position.applyMatrix4(p),M.direction.setFromMatrixPosition(S.matrixWorld),r.setFromMatrixPosition(S.target.matrixWorld),M.direction.sub(r),M.direction.transformDirection(p),m++}else if(S.isRectAreaLight){const M=n.rectArea[_];M.position.setFromMatrixPosition(S.matrixWorld),M.position.applyMatrix4(p),o.identity(),s.copy(S.matrixWorld),s.premultiply(p),o.extractRotation(s),M.halfWidth.set(S.width*.5,0,0),M.halfHeight.set(0,S.height*.5,0),M.halfWidth.applyMatrix4(o),M.halfHeight.applyMatrix4(o),_++}else if(S.isPointLight){const M=n.point[f];M.position.setFromMatrixPosition(S.matrixWorld),M.position.applyMatrix4(p),f++}else if(S.isHemisphereLight){const M=n.hemi[v];M.direction.setFromMatrixPosition(S.matrixWorld),M.direction.transformDirection(p),v++}}}return{setup:a,setupView:u,state:n}}function Za(i){const e=new kp(i),t=[],n=[];function r(d){l.camera=d,t.length=0,n.length=0}function s(d){t.push(d)}function o(d){n.push(d)}function a(){e.setup(t)}function u(d){e.setupView(t,d)}const l={lightsArray:t,shadowsArray:n,camera:null,lights:e,transmissionRenderTarget:{}};return{init:r,state:l,setupLights:a,setupLightsView:u,pushLight:s,pushShadow:o}}function Vp(i){let e=new WeakMap;function t(r,s=0){const o=e.get(r);let a;return o===void 0?(a=new Za(i),e.set(r,[a])):s>=o.length?(a=new Za(i),o.push(a)):a=o[s],a}function n(){e=new WeakMap}return{get:t,dispose:n}}const Gp=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,Wp=`uniform sampler2D shadow_pass;
uniform vec2 resolution;
uniform float radius;
#include <packing>
void main() {
	const float samples = float( VSM_SAMPLES );
	float mean = 0.0;
	float squared_mean = 0.0;
	float uvStride = samples <= 1.0 ? 0.0 : 2.0 / ( samples - 1.0 );
	float uvStart = samples <= 1.0 ? 0.0 : - 1.0;
	for ( float i = 0.0; i < samples; i ++ ) {
		float uvOffset = uvStart + i * uvStride;
		#ifdef HORIZONTAL_PASS
			vec2 distribution = unpackRGBATo2Half( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( uvOffset, 0.0 ) * radius ) / resolution ) );
			mean += distribution.x;
			squared_mean += distribution.y * distribution.y + distribution.x * distribution.x;
		#else
			float depth = unpackRGBAToDepth( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( 0.0, uvOffset ) * radius ) / resolution ) );
			mean += depth;
			squared_mean += depth * depth;
		#endif
	}
	mean = mean / samples;
	squared_mean = squared_mean / samples;
	float std_dev = sqrt( squared_mean - mean * mean );
	gl_FragColor = pack2HalfToRGBA( vec2( mean, std_dev ) );
}`;function Xp(i,e,t){let n=new zo;const r=new Ye,s=new Ye,o=new Mt,a=new su({depthPacking:_c}),u=new ou,l={},d=t.maxTextureSize,h={[Vn]:Wt,[Wt]:Vn,[An]:An},f=new Gn({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new Ye},radius:{value:4}},vertexShader:Gp,fragmentShader:Wp}),m=f.clone();m.defines.HORIZONTAL_PASS=1;const _=new yt;_.setAttribute("position",new Bt(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));const v=new Ft(_,f),p=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=nl;let c=this.type;this.render=function(R,P,I){if(p.enabled===!1||p.autoUpdate===!1&&p.needsUpdate===!1||R.length===0)return;const y=i.getRenderTarget(),E=i.getActiveCubeFace(),w=i.getActiveMipmapLevel(),Q=i.state;Q.setBlending(Hn),Q.buffers.depth.getReversed()?Q.buffers.color.setClear(0,0,0,0):Q.buffers.color.setClear(1,1,1,1),Q.buffers.depth.setTest(!0),Q.setScissorTest(!1);const j=c!==Tn&&this.type===Tn,Z=c===Tn&&this.type!==Tn;for(let re=0,X=R.length;re<X;re++){const ae=R[re],W=ae.shadow;if(W===void 0){console.warn("THREE.WebGLShadowMap:",ae,"has no shadow.");continue}if(W.autoUpdate===!1&&W.needsUpdate===!1)continue;r.copy(W.mapSize);const he=W.getFrameExtents();if(r.multiply(he),s.copy(W.mapSize),(r.x>d||r.y>d)&&(r.x>d&&(s.x=Math.floor(d/he.x),r.x=s.x*he.x,W.mapSize.x=s.x),r.y>d&&(s.y=Math.floor(d/he.y),r.y=s.y*he.y,W.mapSize.y=s.y)),W.map===null||j===!0||Z===!0){const Te=this.type!==Tn?{minFilter:Zt,magFilter:Zt}:{};W.map!==null&&W.map.dispose(),W.map=new ri(r.x,r.y,Te),W.map.texture.name=ae.name+".shadowMap",W.camera.updateProjectionMatrix()}i.setRenderTarget(W.map),i.clear();const ye=W.getViewportCount();for(let Te=0;Te<ye;Te++){const ze=W.getViewport(Te);o.set(s.x*ze.x,s.y*ze.y,s.x*ze.z,s.y*ze.w),Q.viewport(o),W.updateMatrices(ae,Te),n=W.getFrustum(),M(P,I,W.camera,ae,this.type)}W.isPointLightShadow!==!0&&this.type===Tn&&A(W,I),W.needsUpdate=!1}c=this.type,p.needsUpdate=!1,i.setRenderTarget(y,E,w)};function A(R,P){const I=e.update(v);f.defines.VSM_SAMPLES!==R.blurSamples&&(f.defines.VSM_SAMPLES=R.blurSamples,m.defines.VSM_SAMPLES=R.blurSamples,f.needsUpdate=!0,m.needsUpdate=!0),R.mapPass===null&&(R.mapPass=new ri(r.x,r.y)),f.uniforms.shadow_pass.value=R.map.texture,f.uniforms.resolution.value=R.mapSize,f.uniforms.radius.value=R.radius,i.setRenderTarget(R.mapPass),i.clear(),i.renderBufferDirect(P,null,I,f,v,null),m.uniforms.shadow_pass.value=R.mapPass.texture,m.uniforms.resolution.value=R.mapSize,m.uniforms.radius.value=R.radius,i.setRenderTarget(R.map),i.clear(),i.renderBufferDirect(P,null,I,m,v,null)}function S(R,P,I,y){let E=null;const w=I.isPointLight===!0?R.customDistanceMaterial:R.customDepthMaterial;if(w!==void 0)E=w;else if(E=I.isPointLight===!0?u:a,i.localClippingEnabled&&P.clipShadows===!0&&Array.isArray(P.clippingPlanes)&&P.clippingPlanes.length!==0||P.displacementMap&&P.displacementScale!==0||P.alphaMap&&P.alphaTest>0||P.map&&P.alphaTest>0||P.alphaToCoverage===!0){const Q=E.uuid,j=P.uuid;let Z=l[Q];Z===void 0&&(Z={},l[Q]=Z);let re=Z[j];re===void 0&&(re=E.clone(),Z[j]=re,P.addEventListener("dispose",C)),E=re}if(E.visible=P.visible,E.wireframe=P.wireframe,y===Tn?E.side=P.shadowSide!==null?P.shadowSide:P.side:E.side=P.shadowSide!==null?P.shadowSide:h[P.side],E.alphaMap=P.alphaMap,E.alphaTest=P.alphaToCoverage===!0?.5:P.alphaTest,E.map=P.map,E.clipShadows=P.clipShadows,E.clippingPlanes=P.clippingPlanes,E.clipIntersection=P.clipIntersection,E.displacementMap=P.displacementMap,E.displacementScale=P.displacementScale,E.displacementBias=P.displacementBias,E.wireframeLinewidth=P.wireframeLinewidth,E.linewidth=P.linewidth,I.isPointLight===!0&&E.isMeshDistanceMaterial===!0){const Q=i.properties.get(E);Q.light=I}return E}function M(R,P,I,y,E){if(R.visible===!1)return;if(R.layers.test(P.layers)&&(R.isMesh||R.isLine||R.isPoints)&&(R.castShadow||R.receiveShadow&&E===Tn)&&(!R.frustumCulled||n.intersectsObject(R))){R.modelViewMatrix.multiplyMatrices(I.matrixWorldInverse,R.matrixWorld);const j=e.update(R),Z=R.material;if(Array.isArray(Z)){const re=j.groups;for(let X=0,ae=re.length;X<ae;X++){const W=re[X],he=Z[W.materialIndex];if(he&&he.visible){const ye=S(R,he,y,E);R.onBeforeShadow(i,R,P,I,j,ye,W),i.renderBufferDirect(I,null,j,ye,R,W),R.onAfterShadow(i,R,P,I,j,ye,W)}}}else if(Z.visible){const re=S(R,Z,y,E);R.onBeforeShadow(i,R,P,I,j,re,null),i.renderBufferDirect(I,null,j,re,R,null),R.onAfterShadow(i,R,P,I,j,re,null)}}const Q=R.children;for(let j=0,Z=Q.length;j<Z;j++)M(Q[j],P,I,y,E)}function C(R){R.target.removeEventListener("dispose",C);for(const I in l){const y=l[I],E=R.target.uuid;E in y&&(y[E].dispose(),delete y[E])}}}const qp={[Hs]:ks,[Vs]:Xs,[Gs]:qs,[Ui]:Ws,[ks]:Hs,[Xs]:Vs,[qs]:Gs,[Ws]:Ui};function Yp(i,e){function t(){let U=!1;const fe=new Mt;let ge=null;const be=new Mt(0,0,0,0);return{setMask:function(ce){ge!==ce&&!U&&(i.colorMask(ce,ce,ce,ce),ge=ce)},setLocked:function(ce){U=ce},setClear:function(ce,ie,Le,Ve,tt){tt===!0&&(ce*=Ve,ie*=Ve,Le*=Ve),fe.set(ce,ie,Le,Ve),be.equals(fe)===!1&&(i.clearColor(ce,ie,Le,Ve),be.copy(fe))},reset:function(){U=!1,ge=null,be.set(-1,0,0,0)}}}function n(){let U=!1,fe=!1,ge=null,be=null,ce=null;return{setReversed:function(ie){if(fe!==ie){const Le=e.get("EXT_clip_control");ie?Le.clipControlEXT(Le.LOWER_LEFT_EXT,Le.ZERO_TO_ONE_EXT):Le.clipControlEXT(Le.LOWER_LEFT_EXT,Le.NEGATIVE_ONE_TO_ONE_EXT),fe=ie;const Ve=ce;ce=null,this.setClear(Ve)}},getReversed:function(){return fe},setTest:function(ie){ie?D(i.DEPTH_TEST):z(i.DEPTH_TEST)},setMask:function(ie){ge!==ie&&!U&&(i.depthMask(ie),ge=ie)},setFunc:function(ie){if(fe&&(ie=qp[ie]),be!==ie){switch(ie){case Hs:i.depthFunc(i.NEVER);break;case ks:i.depthFunc(i.ALWAYS);break;case Vs:i.depthFunc(i.LESS);break;case Ui:i.depthFunc(i.LEQUAL);break;case Gs:i.depthFunc(i.EQUAL);break;case Ws:i.depthFunc(i.GEQUAL);break;case Xs:i.depthFunc(i.GREATER);break;case qs:i.depthFunc(i.NOTEQUAL);break;default:i.depthFunc(i.LEQUAL)}be=ie}},setLocked:function(ie){U=ie},setClear:function(ie){ce!==ie&&(fe&&(ie=1-ie),i.clearDepth(ie),ce=ie)},reset:function(){U=!1,ge=null,be=null,ce=null,fe=!1}}}function r(){let U=!1,fe=null,ge=null,be=null,ce=null,ie=null,Le=null,Ve=null,tt=null;return{setTest:function(Xe){U||(Xe?D(i.STENCIL_TEST):z(i.STENCIL_TEST))},setMask:function(Xe){fe!==Xe&&!U&&(i.stencilMask(Xe),fe=Xe)},setFunc:function(Xe,$t,Jt){(ge!==Xe||be!==$t||ce!==Jt)&&(i.stencilFunc(Xe,$t,Jt),ge=Xe,be=$t,ce=Jt)},setOp:function(Xe,$t,Jt){(ie!==Xe||Le!==$t||Ve!==Jt)&&(i.stencilOp(Xe,$t,Jt),ie=Xe,Le=$t,Ve=Jt)},setLocked:function(Xe){U=Xe},setClear:function(Xe){tt!==Xe&&(i.clearStencil(Xe),tt=Xe)},reset:function(){U=!1,fe=null,ge=null,be=null,ce=null,ie=null,Le=null,Ve=null,tt=null}}}const s=new t,o=new n,a=new r,u=new WeakMap,l=new WeakMap;let d={},h={},f=new WeakMap,m=[],_=null,v=!1,p=null,c=null,A=null,S=null,M=null,C=null,R=null,P=new je(0,0,0),I=0,y=!1,E=null,w=null,Q=null,j=null,Z=null;const re=i.getParameter(i.MAX_COMBINED_TEXTURE_IMAGE_UNITS);let X=!1,ae=0;const W=i.getParameter(i.VERSION);W.indexOf("WebGL")!==-1?(ae=parseFloat(/^WebGL (\d)/.exec(W)[1]),X=ae>=1):W.indexOf("OpenGL ES")!==-1&&(ae=parseFloat(/^OpenGL ES (\d)/.exec(W)[1]),X=ae>=2);let he=null,ye={};const Te=i.getParameter(i.SCISSOR_BOX),ze=i.getParameter(i.VIEWPORT),nt=new Mt().fromArray(Te),it=new Mt().fromArray(ze);function J(U,fe,ge,be){const ce=new Uint8Array(4),ie=i.createTexture();i.bindTexture(U,ie),i.texParameteri(U,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(U,i.TEXTURE_MAG_FILTER,i.NEAREST);for(let Le=0;Le<ge;Le++)U===i.TEXTURE_3D||U===i.TEXTURE_2D_ARRAY?i.texImage3D(fe,0,i.RGBA,1,1,be,0,i.RGBA,i.UNSIGNED_BYTE,ce):i.texImage2D(fe+Le,0,i.RGBA,1,1,0,i.RGBA,i.UNSIGNED_BYTE,ce);return ie}const L={};L[i.TEXTURE_2D]=J(i.TEXTURE_2D,i.TEXTURE_2D,1),L[i.TEXTURE_CUBE_MAP]=J(i.TEXTURE_CUBE_MAP,i.TEXTURE_CUBE_MAP_POSITIVE_X,6),L[i.TEXTURE_2D_ARRAY]=J(i.TEXTURE_2D_ARRAY,i.TEXTURE_2D_ARRAY,1,1),L[i.TEXTURE_3D]=J(i.TEXTURE_3D,i.TEXTURE_3D,1,1),s.setClear(0,0,0,1),o.setClear(1),a.setClear(0),D(i.DEPTH_TEST),o.setFunc(Ui),me(!1),K(qo),D(i.CULL_FACE),ne(Hn);function D(U){d[U]!==!0&&(i.enable(U),d[U]=!0)}function z(U){d[U]!==!1&&(i.disable(U),d[U]=!1)}function H(U,fe){return h[U]!==fe?(i.bindFramebuffer(U,fe),h[U]=fe,U===i.DRAW_FRAMEBUFFER&&(h[i.FRAMEBUFFER]=fe),U===i.FRAMEBUFFER&&(h[i.DRAW_FRAMEBUFFER]=fe),!0):!1}function G(U,fe){let ge=m,be=!1;if(U){ge=f.get(fe),ge===void 0&&(ge=[],f.set(fe,ge));const ce=U.textures;if(ge.length!==ce.length||ge[0]!==i.COLOR_ATTACHMENT0){for(let ie=0,Le=ce.length;ie<Le;ie++)ge[ie]=i.COLOR_ATTACHMENT0+ie;ge.length=ce.length,be=!0}}else ge[0]!==i.BACK&&(ge[0]=i.BACK,be=!0);be&&i.drawBuffers(ge)}function Y(U){return _!==U?(i.useProgram(U),_=U,!0):!1}const ee={[Qn]:i.FUNC_ADD,[Gl]:i.FUNC_SUBTRACT,[Wl]:i.FUNC_REVERSE_SUBTRACT};ee[Xl]=i.MIN,ee[ql]=i.MAX;const b={[Yl]:i.ZERO,[jl]:i.ONE,[Kl]:i.SRC_COLOR,[Bs]:i.SRC_ALPHA,[tc]:i.SRC_ALPHA_SATURATE,[Ql]:i.DST_COLOR,[$l]:i.DST_ALPHA,[Zl]:i.ONE_MINUS_SRC_COLOR,[zs]:i.ONE_MINUS_SRC_ALPHA,[ec]:i.ONE_MINUS_DST_COLOR,[Jl]:i.ONE_MINUS_DST_ALPHA,[nc]:i.CONSTANT_COLOR,[ic]:i.ONE_MINUS_CONSTANT_COLOR,[rc]:i.CONSTANT_ALPHA,[sc]:i.ONE_MINUS_CONSTANT_ALPHA};function ne(U,fe,ge,be,ce,ie,Le,Ve,tt,Xe){if(U===Hn){v===!0&&(z(i.BLEND),v=!1);return}if(v===!1&&(D(i.BLEND),v=!0),U!==Vl){if(U!==p||Xe!==y){if((c!==Qn||M!==Qn)&&(i.blendEquation(i.FUNC_ADD),c=Qn,M=Qn),Xe)switch(U){case Pi:i.blendFuncSeparate(i.ONE,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Yo:i.blendFunc(i.ONE,i.ONE);break;case jo:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case Ko:i.blendFuncSeparate(i.DST_COLOR,i.ONE_MINUS_SRC_ALPHA,i.ZERO,i.ONE);break;default:console.error("THREE.WebGLState: Invalid blending: ",U);break}else switch(U){case Pi:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Yo:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE,i.ONE,i.ONE);break;case jo:console.error("THREE.WebGLState: SubtractiveBlending requires material.premultipliedAlpha = true");break;case Ko:console.error("THREE.WebGLState: MultiplyBlending requires material.premultipliedAlpha = true");break;default:console.error("THREE.WebGLState: Invalid blending: ",U);break}A=null,S=null,C=null,R=null,P.set(0,0,0),I=0,p=U,y=Xe}return}ce=ce||fe,ie=ie||ge,Le=Le||be,(fe!==c||ce!==M)&&(i.blendEquationSeparate(ee[fe],ee[ce]),c=fe,M=ce),(ge!==A||be!==S||ie!==C||Le!==R)&&(i.blendFuncSeparate(b[ge],b[be],b[ie],b[Le]),A=ge,S=be,C=ie,R=Le),(Ve.equals(P)===!1||tt!==I)&&(i.blendColor(Ve.r,Ve.g,Ve.b,tt),P.copy(Ve),I=tt),p=U,y=!1}function q(U,fe){U.side===An?z(i.CULL_FACE):D(i.CULL_FACE);let ge=U.side===Wt;fe&&(ge=!ge),me(ge),U.blending===Pi&&U.transparent===!1?ne(Hn):ne(U.blending,U.blendEquation,U.blendSrc,U.blendDst,U.blendEquationAlpha,U.blendSrcAlpha,U.blendDstAlpha,U.blendColor,U.blendAlpha,U.premultipliedAlpha),o.setFunc(U.depthFunc),o.setTest(U.depthTest),o.setMask(U.depthWrite),s.setMask(U.colorWrite);const be=U.stencilWrite;a.setTest(be),be&&(a.setMask(U.stencilWriteMask),a.setFunc(U.stencilFunc,U.stencilRef,U.stencilFuncMask),a.setOp(U.stencilFail,U.stencilZFail,U.stencilZPass)),ue(U.polygonOffset,U.polygonOffsetFactor,U.polygonOffsetUnits),U.alphaToCoverage===!0?D(i.SAMPLE_ALPHA_TO_COVERAGE):z(i.SAMPLE_ALPHA_TO_COVERAGE)}function me(U){E!==U&&(U?i.frontFace(i.CW):i.frontFace(i.CCW),E=U)}function K(U){U!==zl?(D(i.CULL_FACE),U!==w&&(U===qo?i.cullFace(i.BACK):U===Hl?i.cullFace(i.FRONT):i.cullFace(i.FRONT_AND_BACK))):z(i.CULL_FACE),w=U}function Ke(U){U!==Q&&(X&&i.lineWidth(U),Q=U)}function ue(U,fe,ge){U?(D(i.POLYGON_OFFSET_FILL),(j!==fe||Z!==ge)&&(i.polygonOffset(fe,ge),j=fe,Z=ge)):z(i.POLYGON_OFFSET_FILL)}function Ce(U){U?D(i.SCISSOR_TEST):z(i.SCISSOR_TEST)}function $e(U){U===void 0&&(U=i.TEXTURE0+re-1),he!==U&&(i.activeTexture(U),he=U)}function Pe(U,fe,ge){ge===void 0&&(he===null?ge=i.TEXTURE0+re-1:ge=he);let be=ye[ge];be===void 0&&(be={type:void 0,texture:void 0},ye[ge]=be),(be.type!==U||be.texture!==fe)&&(he!==ge&&(i.activeTexture(ge),he=ge),i.bindTexture(U,fe||L[U]),be.type=U,be.texture=fe)}function T(){const U=ye[he];U!==void 0&&U.type!==void 0&&(i.bindTexture(U.type,null),U.type=void 0,U.texture=void 0)}function g(){try{i.compressedTexImage2D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function O(){try{i.compressedTexImage3D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function te(){try{i.texSubImage2D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function se(){try{i.texSubImage3D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function $(){try{i.compressedTexSubImage2D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function ve(){try{i.compressedTexSubImage3D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function pe(){try{i.texStorage2D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function we(){try{i.texStorage3D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function Ue(){try{i.texImage2D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function de(){try{i.texImage3D(...arguments)}catch(U){console.error("THREE.WebGLState:",U)}}function xe(U){nt.equals(U)===!1&&(i.scissor(U.x,U.y,U.z,U.w),nt.copy(U))}function Ne(U){it.equals(U)===!1&&(i.viewport(U.x,U.y,U.z,U.w),it.copy(U))}function De(U,fe){let ge=l.get(fe);ge===void 0&&(ge=new WeakMap,l.set(fe,ge));let be=ge.get(U);be===void 0&&(be=i.getUniformBlockIndex(fe,U.name),ge.set(U,be))}function Me(U,fe){const be=l.get(fe).get(U);u.get(fe)!==be&&(i.uniformBlockBinding(fe,be,U.__bindingPointIndex),u.set(fe,be))}function We(){i.disable(i.BLEND),i.disable(i.CULL_FACE),i.disable(i.DEPTH_TEST),i.disable(i.POLYGON_OFFSET_FILL),i.disable(i.SCISSOR_TEST),i.disable(i.STENCIL_TEST),i.disable(i.SAMPLE_ALPHA_TO_COVERAGE),i.blendEquation(i.FUNC_ADD),i.blendFunc(i.ONE,i.ZERO),i.blendFuncSeparate(i.ONE,i.ZERO,i.ONE,i.ZERO),i.blendColor(0,0,0,0),i.colorMask(!0,!0,!0,!0),i.clearColor(0,0,0,0),i.depthMask(!0),i.depthFunc(i.LESS),o.setReversed(!1),i.clearDepth(1),i.stencilMask(4294967295),i.stencilFunc(i.ALWAYS,0,4294967295),i.stencilOp(i.KEEP,i.KEEP,i.KEEP),i.clearStencil(0),i.cullFace(i.BACK),i.frontFace(i.CCW),i.polygonOffset(0,0),i.activeTexture(i.TEXTURE0),i.bindFramebuffer(i.FRAMEBUFFER,null),i.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),i.bindFramebuffer(i.READ_FRAMEBUFFER,null),i.useProgram(null),i.lineWidth(1),i.scissor(0,0,i.canvas.width,i.canvas.height),i.viewport(0,0,i.canvas.width,i.canvas.height),d={},he=null,ye={},h={},f=new WeakMap,m=[],_=null,v=!1,p=null,c=null,A=null,S=null,M=null,C=null,R=null,P=new je(0,0,0),I=0,y=!1,E=null,w=null,Q=null,j=null,Z=null,nt.set(0,0,i.canvas.width,i.canvas.height),it.set(0,0,i.canvas.width,i.canvas.height),s.reset(),o.reset(),a.reset()}return{buffers:{color:s,depth:o,stencil:a},enable:D,disable:z,bindFramebuffer:H,drawBuffers:G,useProgram:Y,setBlending:ne,setMaterial:q,setFlipSided:me,setCullFace:K,setLineWidth:Ke,setPolygonOffset:ue,setScissorTest:Ce,activeTexture:$e,bindTexture:Pe,unbindTexture:T,compressedTexImage2D:g,compressedTexImage3D:O,texImage2D:Ue,texImage3D:de,updateUBOMapping:De,uniformBlockBinding:Me,texStorage2D:pe,texStorage3D:we,texSubImage2D:te,texSubImage3D:se,compressedTexSubImage2D:$,compressedTexSubImage3D:ve,scissor:xe,viewport:Ne,reset:We}}function jp(i,e,t,n,r,s,o){const a=e.has("WEBGL_multisampled_render_to_texture")?e.get("WEBGL_multisampled_render_to_texture"):null,u=typeof navigator>"u"?!1:/OculusBrowser/g.test(navigator.userAgent),l=new Ye,d=new WeakMap;let h;const f=new WeakMap;let m=!1;try{m=typeof OffscreenCanvas<"u"&&new OffscreenCanvas(1,1).getContext("2d")!==null}catch{}function _(T,g){return m?new OffscreenCanvas(T,g):rr("canvas")}function v(T,g,O){let te=1;const se=Pe(T);if((se.width>O||se.height>O)&&(te=O/Math.max(se.width,se.height)),te<1)if(typeof HTMLImageElement<"u"&&T instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&T instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&T instanceof ImageBitmap||typeof VideoFrame<"u"&&T instanceof VideoFrame){const $=Math.floor(te*se.width),ve=Math.floor(te*se.height);h===void 0&&(h=_($,ve));const pe=g?_($,ve):h;return pe.width=$,pe.height=ve,pe.getContext("2d").drawImage(T,0,0,$,ve),console.warn("THREE.WebGLRenderer: Texture has been resized from ("+se.width+"x"+se.height+") to ("+$+"x"+ve+")."),pe}else return"data"in T&&console.warn("THREE.WebGLRenderer: Image in DataTexture is too big ("+se.width+"x"+se.height+")."),T;return T}function p(T){return T.generateMipmaps}function c(T){i.generateMipmap(T)}function A(T){return T.isWebGLCubeRenderTarget?i.TEXTURE_CUBE_MAP:T.isWebGL3DRenderTarget?i.TEXTURE_3D:T.isWebGLArrayRenderTarget||T.isCompressedArrayTexture?i.TEXTURE_2D_ARRAY:i.TEXTURE_2D}function S(T,g,O,te,se=!1){if(T!==null){if(i[T]!==void 0)return i[T];console.warn("THREE.WebGLRenderer: Attempt to use non-existing WebGL internal format '"+T+"'")}let $=g;if(g===i.RED&&(O===i.FLOAT&&($=i.R32F),O===i.HALF_FLOAT&&($=i.R16F),O===i.UNSIGNED_BYTE&&($=i.R8)),g===i.RED_INTEGER&&(O===i.UNSIGNED_BYTE&&($=i.R8UI),O===i.UNSIGNED_SHORT&&($=i.R16UI),O===i.UNSIGNED_INT&&($=i.R32UI),O===i.BYTE&&($=i.R8I),O===i.SHORT&&($=i.R16I),O===i.INT&&($=i.R32I)),g===i.RG&&(O===i.FLOAT&&($=i.RG32F),O===i.HALF_FLOAT&&($=i.RG16F),O===i.UNSIGNED_BYTE&&($=i.RG8)),g===i.RG_INTEGER&&(O===i.UNSIGNED_BYTE&&($=i.RG8UI),O===i.UNSIGNED_SHORT&&($=i.RG16UI),O===i.UNSIGNED_INT&&($=i.RG32UI),O===i.BYTE&&($=i.RG8I),O===i.SHORT&&($=i.RG16I),O===i.INT&&($=i.RG32I)),g===i.RGB_INTEGER&&(O===i.UNSIGNED_BYTE&&($=i.RGB8UI),O===i.UNSIGNED_SHORT&&($=i.RGB16UI),O===i.UNSIGNED_INT&&($=i.RGB32UI),O===i.BYTE&&($=i.RGB8I),O===i.SHORT&&($=i.RGB16I),O===i.INT&&($=i.RGB32I)),g===i.RGBA_INTEGER&&(O===i.UNSIGNED_BYTE&&($=i.RGBA8UI),O===i.UNSIGNED_SHORT&&($=i.RGBA16UI),O===i.UNSIGNED_INT&&($=i.RGBA32UI),O===i.BYTE&&($=i.RGBA8I),O===i.SHORT&&($=i.RGBA16I),O===i.INT&&($=i.RGBA32I)),g===i.RGB&&O===i.UNSIGNED_INT_5_9_9_9_REV&&($=i.RGB9_E5),g===i.RGBA){const ve=se?Wr:at.getTransfer(te);O===i.FLOAT&&($=i.RGBA32F),O===i.HALF_FLOAT&&($=i.RGBA16F),O===i.UNSIGNED_BYTE&&($=ve===ht?i.SRGB8_ALPHA8:i.RGBA8),O===i.UNSIGNED_SHORT_4_4_4_4&&($=i.RGBA4),O===i.UNSIGNED_SHORT_5_5_5_1&&($=i.RGB5_A1)}return($===i.R16F||$===i.R32F||$===i.RG16F||$===i.RG32F||$===i.RGBA16F||$===i.RGBA32F)&&e.get("EXT_color_buffer_float"),$}function M(T,g){let O;return T?g===null||g===ni||g===tr?O=i.DEPTH24_STENCIL8:g===Cn?O=i.DEPTH32F_STENCIL8:g===er&&(O=i.DEPTH24_STENCIL8,console.warn("DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.")):g===null||g===ni||g===tr?O=i.DEPTH_COMPONENT24:g===Cn?O=i.DEPTH_COMPONENT32F:g===er&&(O=i.DEPTH_COMPONENT16),O}function C(T,g){return p(T)===!0||T.isFramebufferTexture&&T.minFilter!==Zt&&T.minFilter!==Gt?Math.log2(Math.max(g.width,g.height))+1:T.mipmaps!==void 0&&T.mipmaps.length>0?T.mipmaps.length:T.isCompressedTexture&&Array.isArray(T.image)?g.mipmaps.length:1}function R(T){const g=T.target;g.removeEventListener("dispose",R),I(g),g.isVideoTexture&&d.delete(g)}function P(T){const g=T.target;g.removeEventListener("dispose",P),E(g)}function I(T){const g=n.get(T);if(g.__webglInit===void 0)return;const O=T.source,te=f.get(O);if(te){const se=te[g.__cacheKey];se.usedTimes--,se.usedTimes===0&&y(T),Object.keys(te).length===0&&f.delete(O)}n.remove(T)}function y(T){const g=n.get(T);i.deleteTexture(g.__webglTexture);const O=T.source,te=f.get(O);delete te[g.__cacheKey],o.memory.textures--}function E(T){const g=n.get(T);if(T.depthTexture&&(T.depthTexture.dispose(),n.remove(T.depthTexture)),T.isWebGLCubeRenderTarget)for(let te=0;te<6;te++){if(Array.isArray(g.__webglFramebuffer[te]))for(let se=0;se<g.__webglFramebuffer[te].length;se++)i.deleteFramebuffer(g.__webglFramebuffer[te][se]);else i.deleteFramebuffer(g.__webglFramebuffer[te]);g.__webglDepthbuffer&&i.deleteRenderbuffer(g.__webglDepthbuffer[te])}else{if(Array.isArray(g.__webglFramebuffer))for(let te=0;te<g.__webglFramebuffer.length;te++)i.deleteFramebuffer(g.__webglFramebuffer[te]);else i.deleteFramebuffer(g.__webglFramebuffer);if(g.__webglDepthbuffer&&i.deleteRenderbuffer(g.__webglDepthbuffer),g.__webglMultisampledFramebuffer&&i.deleteFramebuffer(g.__webglMultisampledFramebuffer),g.__webglColorRenderbuffer)for(let te=0;te<g.__webglColorRenderbuffer.length;te++)g.__webglColorRenderbuffer[te]&&i.deleteRenderbuffer(g.__webglColorRenderbuffer[te]);g.__webglDepthRenderbuffer&&i.deleteRenderbuffer(g.__webglDepthRenderbuffer)}const O=T.textures;for(let te=0,se=O.length;te<se;te++){const $=n.get(O[te]);$.__webglTexture&&(i.deleteTexture($.__webglTexture),o.memory.textures--),n.remove(O[te])}n.remove(T)}let w=0;function Q(){w=0}function j(){const T=w;return T>=r.maxTextures&&console.warn("THREE.WebGLTextures: Trying to use "+T+" texture units while this GPU supports only "+r.maxTextures),w+=1,T}function Z(T){const g=[];return g.push(T.wrapS),g.push(T.wrapT),g.push(T.wrapR||0),g.push(T.magFilter),g.push(T.minFilter),g.push(T.anisotropy),g.push(T.internalFormat),g.push(T.format),g.push(T.type),g.push(T.generateMipmaps),g.push(T.premultiplyAlpha),g.push(T.flipY),g.push(T.unpackAlignment),g.push(T.colorSpace),g.join()}function re(T,g){const O=n.get(T);if(T.isVideoTexture&&Ce(T),T.isRenderTargetTexture===!1&&T.isExternalTexture!==!0&&T.version>0&&O.__version!==T.version){const te=T.image;if(te===null)console.warn("THREE.WebGLRenderer: Texture marked for update but no image data found.");else if(te.complete===!1)console.warn("THREE.WebGLRenderer: Texture marked for update but image is incomplete");else{L(O,T,g);return}}else T.isExternalTexture&&(O.__webglTexture=T.sourceTexture?T.sourceTexture:null);t.bindTexture(i.TEXTURE_2D,O.__webglTexture,i.TEXTURE0+g)}function X(T,g){const O=n.get(T);if(T.isRenderTargetTexture===!1&&T.version>0&&O.__version!==T.version){L(O,T,g);return}t.bindTexture(i.TEXTURE_2D_ARRAY,O.__webglTexture,i.TEXTURE0+g)}function ae(T,g){const O=n.get(T);if(T.isRenderTargetTexture===!1&&T.version>0&&O.__version!==T.version){L(O,T,g);return}t.bindTexture(i.TEXTURE_3D,O.__webglTexture,i.TEXTURE0+g)}function W(T,g){const O=n.get(T);if(T.version>0&&O.__version!==T.version){D(O,T,g);return}t.bindTexture(i.TEXTURE_CUBE_MAP,O.__webglTexture,i.TEXTURE0+g)}const he={[ti]:i.REPEAT,[wn]:i.CLAMP_TO_EDGE,[Qi]:i.MIRRORED_REPEAT},ye={[Zt]:i.NEAREST,[mc]:i.NEAREST_MIPMAP_NEAREST,[ur]:i.NEAREST_MIPMAP_LINEAR,[Gt]:i.LINEAR,[es]:i.LINEAR_MIPMAP_NEAREST,[Rn]:i.LINEAR_MIPMAP_LINEAR},Te={[xc]:i.NEVER,[bc]:i.ALWAYS,[Mc]:i.LESS,[dl]:i.LEQUAL,[Sc]:i.EQUAL,[Tc]:i.GEQUAL,[yc]:i.GREATER,[Ec]:i.NOTEQUAL};function ze(T,g){if(g.type===Cn&&e.has("OES_texture_float_linear")===!1&&(g.magFilter===Gt||g.magFilter===es||g.magFilter===ur||g.magFilter===Rn||g.minFilter===Gt||g.minFilter===es||g.minFilter===ur||g.minFilter===Rn)&&console.warn("THREE.WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device."),i.texParameteri(T,i.TEXTURE_WRAP_S,he[g.wrapS]),i.texParameteri(T,i.TEXTURE_WRAP_T,he[g.wrapT]),(T===i.TEXTURE_3D||T===i.TEXTURE_2D_ARRAY)&&i.texParameteri(T,i.TEXTURE_WRAP_R,he[g.wrapR]),i.texParameteri(T,i.TEXTURE_MAG_FILTER,ye[g.magFilter]),i.texParameteri(T,i.TEXTURE_MIN_FILTER,ye[g.minFilter]),g.compareFunction&&(i.texParameteri(T,i.TEXTURE_COMPARE_MODE,i.COMPARE_REF_TO_TEXTURE),i.texParameteri(T,i.TEXTURE_COMPARE_FUNC,Te[g.compareFunction])),e.has("EXT_texture_filter_anisotropic")===!0){if(g.magFilter===Zt||g.minFilter!==ur&&g.minFilter!==Rn||g.type===Cn&&e.has("OES_texture_float_linear")===!1)return;if(g.anisotropy>1||n.get(g).__currentAnisotropy){const O=e.get("EXT_texture_filter_anisotropic");i.texParameterf(T,O.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(g.anisotropy,r.getMaxAnisotropy())),n.get(g).__currentAnisotropy=g.anisotropy}}}function nt(T,g){let O=!1;T.__webglInit===void 0&&(T.__webglInit=!0,g.addEventListener("dispose",R));const te=g.source;let se=f.get(te);se===void 0&&(se={},f.set(te,se));const $=Z(g);if($!==T.__cacheKey){se[$]===void 0&&(se[$]={texture:i.createTexture(),usedTimes:0},o.memory.textures++,O=!0),se[$].usedTimes++;const ve=se[T.__cacheKey];ve!==void 0&&(se[T.__cacheKey].usedTimes--,ve.usedTimes===0&&y(g)),T.__cacheKey=$,T.__webglTexture=se[$].texture}return O}function it(T,g,O){return Math.floor(Math.floor(T/O)/g)}function J(T,g,O,te){const $=T.updateRanges;if($.length===0)t.texSubImage2D(i.TEXTURE_2D,0,0,0,g.width,g.height,O,te,g.data);else{$.sort((de,xe)=>de.start-xe.start);let ve=0;for(let de=1;de<$.length;de++){const xe=$[ve],Ne=$[de],De=xe.start+xe.count,Me=it(Ne.start,g.width,4),We=it(xe.start,g.width,4);Ne.start<=De+1&&Me===We&&it(Ne.start+Ne.count-1,g.width,4)===Me?xe.count=Math.max(xe.count,Ne.start+Ne.count-xe.start):(++ve,$[ve]=Ne)}$.length=ve+1;const pe=i.getParameter(i.UNPACK_ROW_LENGTH),we=i.getParameter(i.UNPACK_SKIP_PIXELS),Ue=i.getParameter(i.UNPACK_SKIP_ROWS);i.pixelStorei(i.UNPACK_ROW_LENGTH,g.width);for(let de=0,xe=$.length;de<xe;de++){const Ne=$[de],De=Math.floor(Ne.start/4),Me=Math.ceil(Ne.count/4),We=De%g.width,U=Math.floor(De/g.width),fe=Me,ge=1;i.pixelStorei(i.UNPACK_SKIP_PIXELS,We),i.pixelStorei(i.UNPACK_SKIP_ROWS,U),t.texSubImage2D(i.TEXTURE_2D,0,We,U,fe,ge,O,te,g.data)}T.clearUpdateRanges(),i.pixelStorei(i.UNPACK_ROW_LENGTH,pe),i.pixelStorei(i.UNPACK_SKIP_PIXELS,we),i.pixelStorei(i.UNPACK_SKIP_ROWS,Ue)}}function L(T,g,O){let te=i.TEXTURE_2D;(g.isDataArrayTexture||g.isCompressedArrayTexture)&&(te=i.TEXTURE_2D_ARRAY),g.isData3DTexture&&(te=i.TEXTURE_3D);const se=nt(T,g),$=g.source;t.bindTexture(te,T.__webglTexture,i.TEXTURE0+O);const ve=n.get($);if($.version!==ve.__version||se===!0){t.activeTexture(i.TEXTURE0+O);const pe=at.getPrimaries(at.workingColorSpace),we=g.colorSpace===Bn?null:at.getPrimaries(g.colorSpace),Ue=g.colorSpace===Bn||pe===we?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,g.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,g.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,g.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,Ue);let de=v(g.image,!1,r.maxTextureSize);de=$e(g,de);const xe=s.convert(g.format,g.colorSpace),Ne=s.convert(g.type);let De=S(g.internalFormat,xe,Ne,g.colorSpace,g.isVideoTexture);ze(te,g);let Me;const We=g.mipmaps,U=g.isVideoTexture!==!0,fe=ve.__version===void 0||se===!0,ge=$.dataReady,be=C(g,de);if(g.isDepthTexture)De=M(g.format===ir,g.type),fe&&(U?t.texStorage2D(i.TEXTURE_2D,1,De,de.width,de.height):t.texImage2D(i.TEXTURE_2D,0,De,de.width,de.height,0,xe,Ne,null));else if(g.isDataTexture)if(We.length>0){U&&fe&&t.texStorage2D(i.TEXTURE_2D,be,De,We[0].width,We[0].height);for(let ce=0,ie=We.length;ce<ie;ce++)Me=We[ce],U?ge&&t.texSubImage2D(i.TEXTURE_2D,ce,0,0,Me.width,Me.height,xe,Ne,Me.data):t.texImage2D(i.TEXTURE_2D,ce,De,Me.width,Me.height,0,xe,Ne,Me.data);g.generateMipmaps=!1}else U?(fe&&t.texStorage2D(i.TEXTURE_2D,be,De,de.width,de.height),ge&&J(g,de,xe,Ne)):t.texImage2D(i.TEXTURE_2D,0,De,de.width,de.height,0,xe,Ne,de.data);else if(g.isCompressedTexture)if(g.isCompressedArrayTexture){U&&fe&&t.texStorage3D(i.TEXTURE_2D_ARRAY,be,De,We[0].width,We[0].height,de.depth);for(let ce=0,ie=We.length;ce<ie;ce++)if(Me=We[ce],g.format!==dn)if(xe!==null)if(U){if(ge)if(g.layerUpdates.size>0){const Le=Aa(Me.width,Me.height,g.format,g.type);for(const Ve of g.layerUpdates){const tt=Me.data.subarray(Ve*Le/Me.data.BYTES_PER_ELEMENT,(Ve+1)*Le/Me.data.BYTES_PER_ELEMENT);t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ce,0,0,Ve,Me.width,Me.height,1,xe,tt)}g.clearLayerUpdates()}else t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ce,0,0,0,Me.width,Me.height,de.depth,xe,Me.data)}else t.compressedTexImage3D(i.TEXTURE_2D_ARRAY,ce,De,Me.width,Me.height,de.depth,0,Me.data,0,0);else console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()");else U?ge&&t.texSubImage3D(i.TEXTURE_2D_ARRAY,ce,0,0,0,Me.width,Me.height,de.depth,xe,Ne,Me.data):t.texImage3D(i.TEXTURE_2D_ARRAY,ce,De,Me.width,Me.height,de.depth,0,xe,Ne,Me.data)}else{U&&fe&&t.texStorage2D(i.TEXTURE_2D,be,De,We[0].width,We[0].height);for(let ce=0,ie=We.length;ce<ie;ce++)Me=We[ce],g.format!==dn?xe!==null?U?ge&&t.compressedTexSubImage2D(i.TEXTURE_2D,ce,0,0,Me.width,Me.height,xe,Me.data):t.compressedTexImage2D(i.TEXTURE_2D,ce,De,Me.width,Me.height,0,Me.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()"):U?ge&&t.texSubImage2D(i.TEXTURE_2D,ce,0,0,Me.width,Me.height,xe,Ne,Me.data):t.texImage2D(i.TEXTURE_2D,ce,De,Me.width,Me.height,0,xe,Ne,Me.data)}else if(g.isDataArrayTexture)if(U){if(fe&&t.texStorage3D(i.TEXTURE_2D_ARRAY,be,De,de.width,de.height,de.depth),ge)if(g.layerUpdates.size>0){const ce=Aa(de.width,de.height,g.format,g.type);for(const ie of g.layerUpdates){const Le=de.data.subarray(ie*ce/de.data.BYTES_PER_ELEMENT,(ie+1)*ce/de.data.BYTES_PER_ELEMENT);t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,ie,de.width,de.height,1,xe,Ne,Le)}g.clearLayerUpdates()}else t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,0,de.width,de.height,de.depth,xe,Ne,de.data)}else t.texImage3D(i.TEXTURE_2D_ARRAY,0,De,de.width,de.height,de.depth,0,xe,Ne,de.data);else if(g.isData3DTexture)U?(fe&&t.texStorage3D(i.TEXTURE_3D,be,De,de.width,de.height,de.depth),ge&&t.texSubImage3D(i.TEXTURE_3D,0,0,0,0,de.width,de.height,de.depth,xe,Ne,de.data)):t.texImage3D(i.TEXTURE_3D,0,De,de.width,de.height,de.depth,0,xe,Ne,de.data);else if(g.isFramebufferTexture){if(fe)if(U)t.texStorage2D(i.TEXTURE_2D,be,De,de.width,de.height);else{let ce=de.width,ie=de.height;for(let Le=0;Le<be;Le++)t.texImage2D(i.TEXTURE_2D,Le,De,ce,ie,0,xe,Ne,null),ce>>=1,ie>>=1}}else if(We.length>0){if(U&&fe){const ce=Pe(We[0]);t.texStorage2D(i.TEXTURE_2D,be,De,ce.width,ce.height)}for(let ce=0,ie=We.length;ce<ie;ce++)Me=We[ce],U?ge&&t.texSubImage2D(i.TEXTURE_2D,ce,0,0,xe,Ne,Me):t.texImage2D(i.TEXTURE_2D,ce,De,xe,Ne,Me);g.generateMipmaps=!1}else if(U){if(fe){const ce=Pe(de);t.texStorage2D(i.TEXTURE_2D,be,De,ce.width,ce.height)}ge&&t.texSubImage2D(i.TEXTURE_2D,0,0,0,xe,Ne,de)}else t.texImage2D(i.TEXTURE_2D,0,De,xe,Ne,de);p(g)&&c(te),ve.__version=$.version,g.onUpdate&&g.onUpdate(g)}T.__version=g.version}function D(T,g,O){if(g.image.length!==6)return;const te=nt(T,g),se=g.source;t.bindTexture(i.TEXTURE_CUBE_MAP,T.__webglTexture,i.TEXTURE0+O);const $=n.get(se);if(se.version!==$.__version||te===!0){t.activeTexture(i.TEXTURE0+O);const ve=at.getPrimaries(at.workingColorSpace),pe=g.colorSpace===Bn?null:at.getPrimaries(g.colorSpace),we=g.colorSpace===Bn||ve===pe?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,g.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,g.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,g.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,we);const Ue=g.isCompressedTexture||g.image[0].isCompressedTexture,de=g.image[0]&&g.image[0].isDataTexture,xe=[];for(let ie=0;ie<6;ie++)!Ue&&!de?xe[ie]=v(g.image[ie],!0,r.maxCubemapSize):xe[ie]=de?g.image[ie].image:g.image[ie],xe[ie]=$e(g,xe[ie]);const Ne=xe[0],De=s.convert(g.format,g.colorSpace),Me=s.convert(g.type),We=S(g.internalFormat,De,Me,g.colorSpace),U=g.isVideoTexture!==!0,fe=$.__version===void 0||te===!0,ge=se.dataReady;let be=C(g,Ne);ze(i.TEXTURE_CUBE_MAP,g);let ce;if(Ue){U&&fe&&t.texStorage2D(i.TEXTURE_CUBE_MAP,be,We,Ne.width,Ne.height);for(let ie=0;ie<6;ie++){ce=xe[ie].mipmaps;for(let Le=0;Le<ce.length;Le++){const Ve=ce[Le];g.format!==dn?De!==null?U?ge&&t.compressedTexSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le,0,0,Ve.width,Ve.height,De,Ve.data):t.compressedTexImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le,We,Ve.width,Ve.height,0,Ve.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()"):U?ge&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le,0,0,Ve.width,Ve.height,De,Me,Ve.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le,We,Ve.width,Ve.height,0,De,Me,Ve.data)}}}else{if(ce=g.mipmaps,U&&fe){ce.length>0&&be++;const ie=Pe(xe[0]);t.texStorage2D(i.TEXTURE_CUBE_MAP,be,We,ie.width,ie.height)}for(let ie=0;ie<6;ie++)if(de){U?ge&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,0,0,0,xe[ie].width,xe[ie].height,De,Me,xe[ie].data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,0,We,xe[ie].width,xe[ie].height,0,De,Me,xe[ie].data);for(let Le=0;Le<ce.length;Le++){const tt=ce[Le].image[ie].image;U?ge&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le+1,0,0,tt.width,tt.height,De,Me,tt.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le+1,We,tt.width,tt.height,0,De,Me,tt.data)}}else{U?ge&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,0,0,0,De,Me,xe[ie]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,0,We,De,Me,xe[ie]);for(let Le=0;Le<ce.length;Le++){const Ve=ce[Le];U?ge&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le+1,0,0,De,Me,Ve.image[ie]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ie,Le+1,We,De,Me,Ve.image[ie])}}}p(g)&&c(i.TEXTURE_CUBE_MAP),$.__version=se.version,g.onUpdate&&g.onUpdate(g)}T.__version=g.version}function z(T,g,O,te,se,$){const ve=s.convert(O.format,O.colorSpace),pe=s.convert(O.type),we=S(O.internalFormat,ve,pe,O.colorSpace),Ue=n.get(g),de=n.get(O);if(de.__renderTarget=g,!Ue.__hasExternalTextures){const xe=Math.max(1,g.width>>$),Ne=Math.max(1,g.height>>$);se===i.TEXTURE_3D||se===i.TEXTURE_2D_ARRAY?t.texImage3D(se,$,we,xe,Ne,g.depth,0,ve,pe,null):t.texImage2D(se,$,we,xe,Ne,0,ve,pe,null)}t.bindFramebuffer(i.FRAMEBUFFER,T),ue(g)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,te,se,de.__webglTexture,0,Ke(g)):(se===i.TEXTURE_2D||se>=i.TEXTURE_CUBE_MAP_POSITIVE_X&&se<=i.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&i.framebufferTexture2D(i.FRAMEBUFFER,te,se,de.__webglTexture,$),t.bindFramebuffer(i.FRAMEBUFFER,null)}function H(T,g,O){if(i.bindRenderbuffer(i.RENDERBUFFER,T),g.depthBuffer){const te=g.depthTexture,se=te&&te.isDepthTexture?te.type:null,$=M(g.stencilBuffer,se),ve=g.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,pe=Ke(g);ue(g)?a.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,pe,$,g.width,g.height):O?i.renderbufferStorageMultisample(i.RENDERBUFFER,pe,$,g.width,g.height):i.renderbufferStorage(i.RENDERBUFFER,$,g.width,g.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,ve,i.RENDERBUFFER,T)}else{const te=g.textures;for(let se=0;se<te.length;se++){const $=te[se],ve=s.convert($.format,$.colorSpace),pe=s.convert($.type),we=S($.internalFormat,ve,pe,$.colorSpace),Ue=Ke(g);O&&ue(g)===!1?i.renderbufferStorageMultisample(i.RENDERBUFFER,Ue,we,g.width,g.height):ue(g)?a.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,Ue,we,g.width,g.height):i.renderbufferStorage(i.RENDERBUFFER,we,g.width,g.height)}}i.bindRenderbuffer(i.RENDERBUFFER,null)}function G(T,g){if(g&&g.isWebGLCubeRenderTarget)throw new Error("Depth Texture with cube render targets is not supported");if(t.bindFramebuffer(i.FRAMEBUFFER,T),!(g.depthTexture&&g.depthTexture.isDepthTexture))throw new Error("renderTarget.depthTexture must be an instance of THREE.DepthTexture");const te=n.get(g.depthTexture);te.__renderTarget=g,(!te.__webglTexture||g.depthTexture.image.width!==g.width||g.depthTexture.image.height!==g.height)&&(g.depthTexture.image.width=g.width,g.depthTexture.image.height=g.height,g.depthTexture.needsUpdate=!0),re(g.depthTexture,0);const se=te.__webglTexture,$=Ke(g);if(g.depthTexture.format===nr)ue(g)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,se,0,$):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,se,0);else if(g.depthTexture.format===ir)ue(g)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,se,0,$):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,se,0);else throw new Error("Unknown depthTexture format")}function Y(T){const g=n.get(T),O=T.isWebGLCubeRenderTarget===!0;if(g.__boundDepthTexture!==T.depthTexture){const te=T.depthTexture;if(g.__depthDisposeCallback&&g.__depthDisposeCallback(),te){const se=()=>{delete g.__boundDepthTexture,delete g.__depthDisposeCallback,te.removeEventListener("dispose",se)};te.addEventListener("dispose",se),g.__depthDisposeCallback=se}g.__boundDepthTexture=te}if(T.depthTexture&&!g.__autoAllocateDepthBuffer){if(O)throw new Error("target.depthTexture not supported in Cube render targets");const te=T.texture.mipmaps;te&&te.length>0?G(g.__webglFramebuffer[0],T):G(g.__webglFramebuffer,T)}else if(O){g.__webglDepthbuffer=[];for(let te=0;te<6;te++)if(t.bindFramebuffer(i.FRAMEBUFFER,g.__webglFramebuffer[te]),g.__webglDepthbuffer[te]===void 0)g.__webglDepthbuffer[te]=i.createRenderbuffer(),H(g.__webglDepthbuffer[te],T,!1);else{const se=T.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,$=g.__webglDepthbuffer[te];i.bindRenderbuffer(i.RENDERBUFFER,$),i.framebufferRenderbuffer(i.FRAMEBUFFER,se,i.RENDERBUFFER,$)}}else{const te=T.texture.mipmaps;if(te&&te.length>0?t.bindFramebuffer(i.FRAMEBUFFER,g.__webglFramebuffer[0]):t.bindFramebuffer(i.FRAMEBUFFER,g.__webglFramebuffer),g.__webglDepthbuffer===void 0)g.__webglDepthbuffer=i.createRenderbuffer(),H(g.__webglDepthbuffer,T,!1);else{const se=T.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,$=g.__webglDepthbuffer;i.bindRenderbuffer(i.RENDERBUFFER,$),i.framebufferRenderbuffer(i.FRAMEBUFFER,se,i.RENDERBUFFER,$)}}t.bindFramebuffer(i.FRAMEBUFFER,null)}function ee(T,g,O){const te=n.get(T);g!==void 0&&z(te.__webglFramebuffer,T,T.texture,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,0),O!==void 0&&Y(T)}function b(T){const g=T.texture,O=n.get(T),te=n.get(g);T.addEventListener("dispose",P);const se=T.textures,$=T.isWebGLCubeRenderTarget===!0,ve=se.length>1;if(ve||(te.__webglTexture===void 0&&(te.__webglTexture=i.createTexture()),te.__version=g.version,o.memory.textures++),$){O.__webglFramebuffer=[];for(let pe=0;pe<6;pe++)if(g.mipmaps&&g.mipmaps.length>0){O.__webglFramebuffer[pe]=[];for(let we=0;we<g.mipmaps.length;we++)O.__webglFramebuffer[pe][we]=i.createFramebuffer()}else O.__webglFramebuffer[pe]=i.createFramebuffer()}else{if(g.mipmaps&&g.mipmaps.length>0){O.__webglFramebuffer=[];for(let pe=0;pe<g.mipmaps.length;pe++)O.__webglFramebuffer[pe]=i.createFramebuffer()}else O.__webglFramebuffer=i.createFramebuffer();if(ve)for(let pe=0,we=se.length;pe<we;pe++){const Ue=n.get(se[pe]);Ue.__webglTexture===void 0&&(Ue.__webglTexture=i.createTexture(),o.memory.textures++)}if(T.samples>0&&ue(T)===!1){O.__webglMultisampledFramebuffer=i.createFramebuffer(),O.__webglColorRenderbuffer=[],t.bindFramebuffer(i.FRAMEBUFFER,O.__webglMultisampledFramebuffer);for(let pe=0;pe<se.length;pe++){const we=se[pe];O.__webglColorRenderbuffer[pe]=i.createRenderbuffer(),i.bindRenderbuffer(i.RENDERBUFFER,O.__webglColorRenderbuffer[pe]);const Ue=s.convert(we.format,we.colorSpace),de=s.convert(we.type),xe=S(we.internalFormat,Ue,de,we.colorSpace,T.isXRRenderTarget===!0),Ne=Ke(T);i.renderbufferStorageMultisample(i.RENDERBUFFER,Ne,xe,T.width,T.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+pe,i.RENDERBUFFER,O.__webglColorRenderbuffer[pe])}i.bindRenderbuffer(i.RENDERBUFFER,null),T.depthBuffer&&(O.__webglDepthRenderbuffer=i.createRenderbuffer(),H(O.__webglDepthRenderbuffer,T,!0)),t.bindFramebuffer(i.FRAMEBUFFER,null)}}if($){t.bindTexture(i.TEXTURE_CUBE_MAP,te.__webglTexture),ze(i.TEXTURE_CUBE_MAP,g);for(let pe=0;pe<6;pe++)if(g.mipmaps&&g.mipmaps.length>0)for(let we=0;we<g.mipmaps.length;we++)z(O.__webglFramebuffer[pe][we],T,g,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+pe,we);else z(O.__webglFramebuffer[pe],T,g,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+pe,0);p(g)&&c(i.TEXTURE_CUBE_MAP),t.unbindTexture()}else if(ve){for(let pe=0,we=se.length;pe<we;pe++){const Ue=se[pe],de=n.get(Ue);let xe=i.TEXTURE_2D;(T.isWebGL3DRenderTarget||T.isWebGLArrayRenderTarget)&&(xe=T.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),t.bindTexture(xe,de.__webglTexture),ze(xe,Ue),z(O.__webglFramebuffer,T,Ue,i.COLOR_ATTACHMENT0+pe,xe,0),p(Ue)&&c(xe)}t.unbindTexture()}else{let pe=i.TEXTURE_2D;if((T.isWebGL3DRenderTarget||T.isWebGLArrayRenderTarget)&&(pe=T.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),t.bindTexture(pe,te.__webglTexture),ze(pe,g),g.mipmaps&&g.mipmaps.length>0)for(let we=0;we<g.mipmaps.length;we++)z(O.__webglFramebuffer[we],T,g,i.COLOR_ATTACHMENT0,pe,we);else z(O.__webglFramebuffer,T,g,i.COLOR_ATTACHMENT0,pe,0);p(g)&&c(pe),t.unbindTexture()}T.depthBuffer&&Y(T)}function ne(T){const g=T.textures;for(let O=0,te=g.length;O<te;O++){const se=g[O];if(p(se)){const $=A(T),ve=n.get(se).__webglTexture;t.bindTexture($,ve),c($),t.unbindTexture()}}}const q=[],me=[];function K(T){if(T.samples>0){if(ue(T)===!1){const g=T.textures,O=T.width,te=T.height;let se=i.COLOR_BUFFER_BIT;const $=T.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,ve=n.get(T),pe=g.length>1;if(pe)for(let Ue=0;Ue<g.length;Ue++)t.bindFramebuffer(i.FRAMEBUFFER,ve.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+Ue,i.RENDERBUFFER,null),t.bindFramebuffer(i.FRAMEBUFFER,ve.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+Ue,i.TEXTURE_2D,null,0);t.bindFramebuffer(i.READ_FRAMEBUFFER,ve.__webglMultisampledFramebuffer);const we=T.texture.mipmaps;we&&we.length>0?t.bindFramebuffer(i.DRAW_FRAMEBUFFER,ve.__webglFramebuffer[0]):t.bindFramebuffer(i.DRAW_FRAMEBUFFER,ve.__webglFramebuffer);for(let Ue=0;Ue<g.length;Ue++){if(T.resolveDepthBuffer&&(T.depthBuffer&&(se|=i.DEPTH_BUFFER_BIT),T.stencilBuffer&&T.resolveStencilBuffer&&(se|=i.STENCIL_BUFFER_BIT)),pe){i.framebufferRenderbuffer(i.READ_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.RENDERBUFFER,ve.__webglColorRenderbuffer[Ue]);const de=n.get(g[Ue]).__webglTexture;i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,de,0)}i.blitFramebuffer(0,0,O,te,0,0,O,te,se,i.NEAREST),u===!0&&(q.length=0,me.length=0,q.push(i.COLOR_ATTACHMENT0+Ue),T.depthBuffer&&T.resolveDepthBuffer===!1&&(q.push($),me.push($),i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,me)),i.invalidateFramebuffer(i.READ_FRAMEBUFFER,q))}if(t.bindFramebuffer(i.READ_FRAMEBUFFER,null),t.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),pe)for(let Ue=0;Ue<g.length;Ue++){t.bindFramebuffer(i.FRAMEBUFFER,ve.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+Ue,i.RENDERBUFFER,ve.__webglColorRenderbuffer[Ue]);const de=n.get(g[Ue]).__webglTexture;t.bindFramebuffer(i.FRAMEBUFFER,ve.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+Ue,i.TEXTURE_2D,de,0)}t.bindFramebuffer(i.DRAW_FRAMEBUFFER,ve.__webglMultisampledFramebuffer)}else if(T.depthBuffer&&T.resolveDepthBuffer===!1&&u){const g=T.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,[g])}}}function Ke(T){return Math.min(r.maxSamples,T.samples)}function ue(T){const g=n.get(T);return T.samples>0&&e.has("WEBGL_multisampled_render_to_texture")===!0&&g.__useRenderToTexture!==!1}function Ce(T){const g=o.render.frame;d.get(T)!==g&&(d.set(T,g),T.update())}function $e(T,g){const O=T.colorSpace,te=T.format,se=T.type;return T.isCompressedTexture===!0||T.isVideoTexture===!0||O!==Fi&&O!==Bn&&(at.getTransfer(O)===ht?(te!==dn||se!==_n)&&console.warn("THREE.WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType."):console.error("THREE.WebGLTextures: Unsupported texture color space:",O)),g}function Pe(T){return typeof HTMLImageElement<"u"&&T instanceof HTMLImageElement?(l.width=T.naturalWidth||T.width,l.height=T.naturalHeight||T.height):typeof VideoFrame<"u"&&T instanceof VideoFrame?(l.width=T.displayWidth,l.height=T.displayHeight):(l.width=T.width,l.height=T.height),l}this.allocateTextureUnit=j,this.resetTextureUnits=Q,this.setTexture2D=re,this.setTexture2DArray=X,this.setTexture3D=ae,this.setTextureCube=W,this.rebindTextures=ee,this.setupRenderTarget=b,this.updateRenderTargetMipmap=ne,this.updateMultisampleRenderTarget=K,this.setupDepthRenderbuffer=Y,this.setupFrameBufferTexture=z,this.useMultisampledRTT=ue}function Kp(i,e){function t(n,r=Bn){let s;const o=at.getTransfer(r);if(n===_n)return i.UNSIGNED_BYTE;if(n===Po)return i.UNSIGNED_SHORT_4_4_4_4;if(n===Do)return i.UNSIGNED_SHORT_5_5_5_1;if(n===ol)return i.UNSIGNED_INT_5_9_9_9_REV;if(n===rl)return i.BYTE;if(n===sl)return i.SHORT;if(n===er)return i.UNSIGNED_SHORT;if(n===Co)return i.INT;if(n===ni)return i.UNSIGNED_INT;if(n===Cn)return i.FLOAT;if(n===or)return i.HALF_FLOAT;if(n===al)return i.ALPHA;if(n===ll)return i.RGB;if(n===dn)return i.RGBA;if(n===nr)return i.DEPTH_COMPONENT;if(n===ir)return i.DEPTH_STENCIL;if(n===cl)return i.RED;if(n===Lo)return i.RED_INTEGER;if(n===ul)return i.RG;if(n===Uo)return i.RG_INTEGER;if(n===Io)return i.RGBA_INTEGER;if(n===Br||n===zr||n===Hr||n===kr)if(o===ht)if(s=e.get("WEBGL_compressed_texture_s3tc_srgb"),s!==null){if(n===Br)return s.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===zr)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===Hr)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===kr)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(s=e.get("WEBGL_compressed_texture_s3tc"),s!==null){if(n===Br)return s.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===zr)return s.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===Hr)return s.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===kr)return s.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===Ks||n===Zs||n===$s||n===Js)if(s=e.get("WEBGL_compressed_texture_pvrtc"),s!==null){if(n===Ks)return s.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===Zs)return s.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===$s)return s.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===Js)return s.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===Qs||n===eo||n===to)if(s=e.get("WEBGL_compressed_texture_etc"),s!==null){if(n===Qs||n===eo)return o===ht?s.COMPRESSED_SRGB8_ETC2:s.COMPRESSED_RGB8_ETC2;if(n===to)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:s.COMPRESSED_RGBA8_ETC2_EAC}else return null;if(n===no||n===io||n===ro||n===so||n===oo||n===ao||n===lo||n===co||n===uo||n===ho||n===fo||n===po||n===mo||n===go)if(s=e.get("WEBGL_compressed_texture_astc"),s!==null){if(n===no)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:s.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===io)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:s.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===ro)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:s.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===so)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:s.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===oo)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:s.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===ao)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:s.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===lo)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:s.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===co)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:s.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===uo)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:s.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===ho)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:s.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===fo)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:s.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===po)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:s.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===mo)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:s.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===go)return o===ht?s.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:s.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===Vr||n===_o||n===vo)if(s=e.get("EXT_texture_compression_bptc"),s!==null){if(n===Vr)return o===ht?s.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:s.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===_o)return s.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===vo)return s.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===hl||n===xo||n===Mo||n===So)if(s=e.get("EXT_texture_compression_rgtc"),s!==null){if(n===Vr)return s.COMPRESSED_RED_RGTC1_EXT;if(n===xo)return s.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===Mo)return s.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===So)return s.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===tr?i.UNSIGNED_INT_24_8:i[n]!==void 0?i[n]:null}return{convert:t}}class Dl extends Ot{constructor(e=null){super(),this.sourceTexture=e,this.isExternalTexture=!0}}const Zp=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,$p=`
uniform sampler2DArray depthColor;
uniform float depthWidth;
uniform float depthHeight;

void main() {

	vec2 coord = vec2( gl_FragCoord.x / depthWidth, gl_FragCoord.y / depthHeight );

	if ( coord.x >= 1.0 ) {

		gl_FragDepth = texture( depthColor, vec3( coord.x - 1.0, coord.y, 1 ) ).r;

	} else {

		gl_FragDepth = texture( depthColor, vec3( coord.x, coord.y, 0 ) ).r;

	}

}`;class Jp{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(e,t){if(this.texture===null){const n=new Dl(e.texture);(e.depthNear!==t.depthNear||e.depthFar!==t.depthFar)&&(this.depthNear=e.depthNear,this.depthFar=e.depthFar),this.texture=n}}getMesh(e){if(this.texture!==null&&this.mesh===null){const t=e.cameras[0].viewport,n=new Gn({vertexShader:Zp,fragmentShader:$p,uniforms:{depthColor:{value:this.texture},depthWidth:{value:t.z},depthHeight:{value:t.w}}});this.mesh=new Ft(new $r(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}}class Qp extends si{constructor(e,t){super();const n=this;let r=null,s=1,o=null,a="local-floor",u=1,l=null,d=null,h=null,f=null,m=null,_=null;const v=new Jp,p={},c=t.getContextAttributes();let A=null,S=null;const M=[],C=[],R=new Ye;let P=null;const I=new sn;I.viewport=new Mt;const y=new sn;y.viewport=new Mt;const E=[I,y],w=new mu;let Q=null,j=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function(J){let L=M[J];return L===void 0&&(L=new ys,M[J]=L),L.getTargetRaySpace()},this.getControllerGrip=function(J){let L=M[J];return L===void 0&&(L=new ys,M[J]=L),L.getGripSpace()},this.getHand=function(J){let L=M[J];return L===void 0&&(L=new ys,M[J]=L),L.getHandSpace()};function Z(J){const L=C.indexOf(J.inputSource);if(L===-1)return;const D=M[L];D!==void 0&&(D.update(J.inputSource,J.frame,l||o),D.dispatchEvent({type:J.type,data:J.inputSource}))}function re(){r.removeEventListener("select",Z),r.removeEventListener("selectstart",Z),r.removeEventListener("selectend",Z),r.removeEventListener("squeeze",Z),r.removeEventListener("squeezestart",Z),r.removeEventListener("squeezeend",Z),r.removeEventListener("end",re),r.removeEventListener("inputsourceschange",X);for(let J=0;J<M.length;J++){const L=C[J];L!==null&&(C[J]=null,M[J].disconnect(L))}Q=null,j=null,v.reset();for(const J in p)delete p[J];e.setRenderTarget(A),m=null,f=null,h=null,r=null,S=null,it.stop(),n.isPresenting=!1,e.setPixelRatio(P),e.setSize(R.width,R.height,!1),n.dispatchEvent({type:"sessionend"})}this.setFramebufferScaleFactor=function(J){s=J,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change framebuffer scale while presenting.")},this.setReferenceSpaceType=function(J){a=J,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change reference space type while presenting.")},this.getReferenceSpace=function(){return l||o},this.setReferenceSpace=function(J){l=J},this.getBaseLayer=function(){return f!==null?f:m},this.getBinding=function(){return h},this.getFrame=function(){return _},this.getSession=function(){return r},this.setSession=async function(J){if(r=J,r!==null){if(A=e.getRenderTarget(),r.addEventListener("select",Z),r.addEventListener("selectstart",Z),r.addEventListener("selectend",Z),r.addEventListener("squeeze",Z),r.addEventListener("squeezestart",Z),r.addEventListener("squeezeend",Z),r.addEventListener("end",re),r.addEventListener("inputsourceschange",X),c.xrCompatible!==!0&&await t.makeXRCompatible(),P=e.getPixelRatio(),e.getSize(R),typeof XRWebGLBinding<"u"&&(h=new XRWebGLBinding(r,t)),h!==null&&"createProjectionLayer"in XRWebGLBinding.prototype){let D=null,z=null,H=null;c.depth&&(H=c.stencil?t.DEPTH24_STENCIL8:t.DEPTH_COMPONENT24,D=c.stencil?ir:nr,z=c.stencil?tr:ni);const G={colorFormat:t.RGBA8,depthFormat:H,scaleFactor:s};f=h.createProjectionLayer(G),r.updateRenderState({layers:[f]}),e.setPixelRatio(1),e.setSize(f.textureWidth,f.textureHeight,!1),S=new ri(f.textureWidth,f.textureHeight,{format:dn,type:_n,depthTexture:new yl(f.textureWidth,f.textureHeight,z,void 0,void 0,void 0,void 0,void 0,void 0,D),stencilBuffer:c.stencil,colorSpace:e.outputColorSpace,samples:c.antialias?4:0,resolveDepthBuffer:f.ignoreDepthValues===!1,resolveStencilBuffer:f.ignoreDepthValues===!1})}else{const D={antialias:c.antialias,alpha:!0,depth:c.depth,stencil:c.stencil,framebufferScaleFactor:s};m=new XRWebGLLayer(r,t,D),r.updateRenderState({baseLayer:m}),e.setPixelRatio(1),e.setSize(m.framebufferWidth,m.framebufferHeight,!1),S=new ri(m.framebufferWidth,m.framebufferHeight,{format:dn,type:_n,colorSpace:e.outputColorSpace,stencilBuffer:c.stencil,resolveDepthBuffer:m.ignoreDepthValues===!1,resolveStencilBuffer:m.ignoreDepthValues===!1})}S.isXRRenderTarget=!0,this.setFoveation(u),l=null,o=await r.requestReferenceSpace(a),it.setContext(r),it.start(),n.isPresenting=!0,n.dispatchEvent({type:"sessionstart"})}},this.getEnvironmentBlendMode=function(){if(r!==null)return r.environmentBlendMode},this.getDepthTexture=function(){return v.getDepthTexture()};function X(J){for(let L=0;L<J.removed.length;L++){const D=J.removed[L],z=C.indexOf(D);z>=0&&(C[z]=null,M[z].disconnect(D))}for(let L=0;L<J.added.length;L++){const D=J.added[L];let z=C.indexOf(D);if(z===-1){for(let G=0;G<M.length;G++)if(G>=C.length){C.push(D),z=G;break}else if(C[G]===null){C[G]=D,z=G;break}if(z===-1)break}const H=M[z];H&&H.connect(D)}}const ae=new B,W=new B;function he(J,L,D){ae.setFromMatrixPosition(L.matrixWorld),W.setFromMatrixPosition(D.matrixWorld);const z=ae.distanceTo(W),H=L.projectionMatrix.elements,G=D.projectionMatrix.elements,Y=H[14]/(H[10]-1),ee=H[14]/(H[10]+1),b=(H[9]+1)/H[5],ne=(H[9]-1)/H[5],q=(H[8]-1)/H[0],me=(G[8]+1)/G[0],K=Y*q,Ke=Y*me,ue=z/(-q+me),Ce=ue*-q;if(L.matrixWorld.decompose(J.position,J.quaternion,J.scale),J.translateX(Ce),J.translateZ(ue),J.matrixWorld.compose(J.position,J.quaternion,J.scale),J.matrixWorldInverse.copy(J.matrixWorld).invert(),H[10]===-1)J.projectionMatrix.copy(L.projectionMatrix),J.projectionMatrixInverse.copy(L.projectionMatrixInverse);else{const $e=Y+ue,Pe=ee+ue,T=K-Ce,g=Ke+(z-Ce),O=b*ee/Pe*$e,te=ne*ee/Pe*$e;J.projectionMatrix.makePerspective(T,g,O,te,$e,Pe),J.projectionMatrixInverse.copy(J.projectionMatrix).invert()}}function ye(J,L){L===null?J.matrixWorld.copy(J.matrix):J.matrixWorld.multiplyMatrices(L.matrixWorld,J.matrix),J.matrixWorldInverse.copy(J.matrixWorld).invert()}this.updateCamera=function(J){if(r===null)return;let L=J.near,D=J.far;v.texture!==null&&(v.depthNear>0&&(L=v.depthNear),v.depthFar>0&&(D=v.depthFar)),w.near=y.near=I.near=L,w.far=y.far=I.far=D,(Q!==w.near||j!==w.far)&&(r.updateRenderState({depthNear:w.near,depthFar:w.far}),Q=w.near,j=w.far),w.layers.mask=J.layers.mask|6,I.layers.mask=w.layers.mask&3,y.layers.mask=w.layers.mask&5;const z=J.parent,H=w.cameras;ye(w,z);for(let G=0;G<H.length;G++)ye(H[G],z);H.length===2?he(w,I,y):w.projectionMatrix.copy(I.projectionMatrix),Te(J,w,z)};function Te(J,L,D){D===null?J.matrix.copy(L.matrixWorld):(J.matrix.copy(D.matrixWorld),J.matrix.invert(),J.matrix.multiply(L.matrixWorld)),J.matrix.decompose(J.position,J.quaternion,J.scale),J.updateMatrixWorld(!0),J.projectionMatrix.copy(L.projectionMatrix),J.projectionMatrixInverse.copy(L.projectionMatrixInverse),J.isPerspectiveCamera&&(J.fov=yo*2*Math.atan(1/J.projectionMatrix.elements[5]),J.zoom=1)}this.getCamera=function(){return w},this.getFoveation=function(){if(!(f===null&&m===null))return u},this.setFoveation=function(J){u=J,f!==null&&(f.fixedFoveation=J),m!==null&&m.fixedFoveation!==void 0&&(m.fixedFoveation=J)},this.hasDepthSensing=function(){return v.texture!==null},this.getDepthSensingMesh=function(){return v.getMesh(w)},this.getCameraTexture=function(J){return p[J]};let ze=null;function nt(J,L){if(d=L.getViewerPose(l||o),_=L,d!==null){const D=d.views;m!==null&&(e.setRenderTargetFramebuffer(S,m.framebuffer),e.setRenderTarget(S));let z=!1;D.length!==w.cameras.length&&(w.cameras.length=0,z=!0);for(let ee=0;ee<D.length;ee++){const b=D[ee];let ne=null;if(m!==null)ne=m.getViewport(b);else{const me=h.getViewSubImage(f,b);ne=me.viewport,ee===0&&(e.setRenderTargetTextures(S,me.colorTexture,me.depthStencilTexture),e.setRenderTarget(S))}let q=E[ee];q===void 0&&(q=new sn,q.layers.enable(ee),q.viewport=new Mt,E[ee]=q),q.matrix.fromArray(b.transform.matrix),q.matrix.decompose(q.position,q.quaternion,q.scale),q.projectionMatrix.fromArray(b.projectionMatrix),q.projectionMatrixInverse.copy(q.projectionMatrix).invert(),q.viewport.set(ne.x,ne.y,ne.width,ne.height),ee===0&&(w.matrix.copy(q.matrix),w.matrix.decompose(w.position,w.quaternion,w.scale)),z===!0&&w.cameras.push(q)}const H=r.enabledFeatures;if(H&&H.includes("depth-sensing")&&r.depthUsage=="gpu-optimized"&&h){const ee=h.getDepthInformation(D[0]);ee&&ee.isValid&&ee.texture&&v.init(ee,r.renderState)}if(H&&H.includes("camera-access")&&(e.state.unbindTexture(),h))for(let ee=0;ee<D.length;ee++){const b=D[ee].camera;if(b){let ne=p[b];ne||(ne=new Dl,p[b]=ne);const q=h.getCameraImage(b);ne.sourceTexture=q}}}for(let D=0;D<M.length;D++){const z=C[D],H=M[D];z!==null&&H!==void 0&&H.update(z,L,l||o)}ze&&ze(J,L),L.detectedPlanes&&n.dispatchEvent({type:"planesdetected",data:L}),_=null}const it=new Al;it.setAnimationLoop(nt),this.setAnimationLoop=function(J){ze=J},this.dispose=function(){}}}const $n=new fn,em=new gt;function tm(i,e){function t(p,c){p.matrixAutoUpdate===!0&&p.updateMatrix(),c.value.copy(p.matrix)}function n(p,c){c.color.getRGB(p.fogColor.value,vl(i)),c.isFog?(p.fogNear.value=c.near,p.fogFar.value=c.far):c.isFogExp2&&(p.fogDensity.value=c.density)}function r(p,c,A,S,M){c.isMeshBasicMaterial||c.isMeshLambertMaterial?s(p,c):c.isMeshToonMaterial?(s(p,c),h(p,c)):c.isMeshPhongMaterial?(s(p,c),d(p,c)):c.isMeshStandardMaterial?(s(p,c),f(p,c),c.isMeshPhysicalMaterial&&m(p,c,M)):c.isMeshMatcapMaterial?(s(p,c),_(p,c)):c.isMeshDepthMaterial?s(p,c):c.isMeshDistanceMaterial?(s(p,c),v(p,c)):c.isMeshNormalMaterial?s(p,c):c.isLineBasicMaterial?(o(p,c),c.isLineDashedMaterial&&a(p,c)):c.isPointsMaterial?u(p,c,A,S):c.isSpriteMaterial?l(p,c):c.isShadowMaterial?(p.color.value.copy(c.color),p.opacity.value=c.opacity):c.isShaderMaterial&&(c.uniformsNeedUpdate=!1)}function s(p,c){p.opacity.value=c.opacity,c.color&&p.diffuse.value.copy(c.color),c.emissive&&p.emissive.value.copy(c.emissive).multiplyScalar(c.emissiveIntensity),c.map&&(p.map.value=c.map,t(c.map,p.mapTransform)),c.alphaMap&&(p.alphaMap.value=c.alphaMap,t(c.alphaMap,p.alphaMapTransform)),c.bumpMap&&(p.bumpMap.value=c.bumpMap,t(c.bumpMap,p.bumpMapTransform),p.bumpScale.value=c.bumpScale,c.side===Wt&&(p.bumpScale.value*=-1)),c.normalMap&&(p.normalMap.value=c.normalMap,t(c.normalMap,p.normalMapTransform),p.normalScale.value.copy(c.normalScale),c.side===Wt&&p.normalScale.value.negate()),c.displacementMap&&(p.displacementMap.value=c.displacementMap,t(c.displacementMap,p.displacementMapTransform),p.displacementScale.value=c.displacementScale,p.displacementBias.value=c.displacementBias),c.emissiveMap&&(p.emissiveMap.value=c.emissiveMap,t(c.emissiveMap,p.emissiveMapTransform)),c.specularMap&&(p.specularMap.value=c.specularMap,t(c.specularMap,p.specularMapTransform)),c.alphaTest>0&&(p.alphaTest.value=c.alphaTest);const A=e.get(c),S=A.envMap,M=A.envMapRotation;S&&(p.envMap.value=S,$n.copy(M),$n.x*=-1,$n.y*=-1,$n.z*=-1,S.isCubeTexture&&S.isRenderTargetTexture===!1&&($n.y*=-1,$n.z*=-1),p.envMapRotation.value.setFromMatrix4(em.makeRotationFromEuler($n)),p.flipEnvMap.value=S.isCubeTexture&&S.isRenderTargetTexture===!1?-1:1,p.reflectivity.value=c.reflectivity,p.ior.value=c.ior,p.refractionRatio.value=c.refractionRatio),c.lightMap&&(p.lightMap.value=c.lightMap,p.lightMapIntensity.value=c.lightMapIntensity,t(c.lightMap,p.lightMapTransform)),c.aoMap&&(p.aoMap.value=c.aoMap,p.aoMapIntensity.value=c.aoMapIntensity,t(c.aoMap,p.aoMapTransform))}function o(p,c){p.diffuse.value.copy(c.color),p.opacity.value=c.opacity,c.map&&(p.map.value=c.map,t(c.map,p.mapTransform))}function a(p,c){p.dashSize.value=c.dashSize,p.totalSize.value=c.dashSize+c.gapSize,p.scale.value=c.scale}function u(p,c,A,S){p.diffuse.value.copy(c.color),p.opacity.value=c.opacity,p.size.value=c.size*A,p.scale.value=S*.5,c.map&&(p.map.value=c.map,t(c.map,p.uvTransform)),c.alphaMap&&(p.alphaMap.value=c.alphaMap,t(c.alphaMap,p.alphaMapTransform)),c.alphaTest>0&&(p.alphaTest.value=c.alphaTest)}function l(p,c){p.diffuse.value.copy(c.color),p.opacity.value=c.opacity,p.rotation.value=c.rotation,c.map&&(p.map.value=c.map,t(c.map,p.mapTransform)),c.alphaMap&&(p.alphaMap.value=c.alphaMap,t(c.alphaMap,p.alphaMapTransform)),c.alphaTest>0&&(p.alphaTest.value=c.alphaTest)}function d(p,c){p.specular.value.copy(c.specular),p.shininess.value=Math.max(c.shininess,1e-4)}function h(p,c){c.gradientMap&&(p.gradientMap.value=c.gradientMap)}function f(p,c){p.metalness.value=c.metalness,c.metalnessMap&&(p.metalnessMap.value=c.metalnessMap,t(c.metalnessMap,p.metalnessMapTransform)),p.roughness.value=c.roughness,c.roughnessMap&&(p.roughnessMap.value=c.roughnessMap,t(c.roughnessMap,p.roughnessMapTransform)),c.envMap&&(p.envMapIntensity.value=c.envMapIntensity)}function m(p,c,A){p.ior.value=c.ior,c.sheen>0&&(p.sheenColor.value.copy(c.sheenColor).multiplyScalar(c.sheen),p.sheenRoughness.value=c.sheenRoughness,c.sheenColorMap&&(p.sheenColorMap.value=c.sheenColorMap,t(c.sheenColorMap,p.sheenColorMapTransform)),c.sheenRoughnessMap&&(p.sheenRoughnessMap.value=c.sheenRoughnessMap,t(c.sheenRoughnessMap,p.sheenRoughnessMapTransform))),c.clearcoat>0&&(p.clearcoat.value=c.clearcoat,p.clearcoatRoughness.value=c.clearcoatRoughness,c.clearcoatMap&&(p.clearcoatMap.value=c.clearcoatMap,t(c.clearcoatMap,p.clearcoatMapTransform)),c.clearcoatRoughnessMap&&(p.clearcoatRoughnessMap.value=c.clearcoatRoughnessMap,t(c.clearcoatRoughnessMap,p.clearcoatRoughnessMapTransform)),c.clearcoatNormalMap&&(p.clearcoatNormalMap.value=c.clearcoatNormalMap,t(c.clearcoatNormalMap,p.clearcoatNormalMapTransform),p.clearcoatNormalScale.value.copy(c.clearcoatNormalScale),c.side===Wt&&p.clearcoatNormalScale.value.negate())),c.dispersion>0&&(p.dispersion.value=c.dispersion),c.iridescence>0&&(p.iridescence.value=c.iridescence,p.iridescenceIOR.value=c.iridescenceIOR,p.iridescenceThicknessMinimum.value=c.iridescenceThicknessRange[0],p.iridescenceThicknessMaximum.value=c.iridescenceThicknessRange[1],c.iridescenceMap&&(p.iridescenceMap.value=c.iridescenceMap,t(c.iridescenceMap,p.iridescenceMapTransform)),c.iridescenceThicknessMap&&(p.iridescenceThicknessMap.value=c.iridescenceThicknessMap,t(c.iridescenceThicknessMap,p.iridescenceThicknessMapTransform))),c.transmission>0&&(p.transmission.value=c.transmission,p.transmissionSamplerMap.value=A.texture,p.transmissionSamplerSize.value.set(A.width,A.height),c.transmissionMap&&(p.transmissionMap.value=c.transmissionMap,t(c.transmissionMap,p.transmissionMapTransform)),p.thickness.value=c.thickness,c.thicknessMap&&(p.thicknessMap.value=c.thicknessMap,t(c.thicknessMap,p.thicknessMapTransform)),p.attenuationDistance.value=c.attenuationDistance,p.attenuationColor.value.copy(c.attenuationColor)),c.anisotropy>0&&(p.anisotropyVector.value.set(c.anisotropy*Math.cos(c.anisotropyRotation),c.anisotropy*Math.sin(c.anisotropyRotation)),c.anisotropyMap&&(p.anisotropyMap.value=c.anisotropyMap,t(c.anisotropyMap,p.anisotropyMapTransform))),p.specularIntensity.value=c.specularIntensity,p.specularColor.value.copy(c.specularColor),c.specularColorMap&&(p.specularColorMap.value=c.specularColorMap,t(c.specularColorMap,p.specularColorMapTransform)),c.specularIntensityMap&&(p.specularIntensityMap.value=c.specularIntensityMap,t(c.specularIntensityMap,p.specularIntensityMapTransform))}function _(p,c){c.matcap&&(p.matcap.value=c.matcap)}function v(p,c){const A=e.get(c).light;p.referencePosition.value.setFromMatrixPosition(A.matrixWorld),p.nearDistance.value=A.shadow.camera.near,p.farDistance.value=A.shadow.camera.far}return{refreshFogUniforms:n,refreshMaterialUniforms:r}}function nm(i,e,t,n){let r={},s={},o=[];const a=i.getParameter(i.MAX_UNIFORM_BUFFER_BINDINGS);function u(A,S){const M=S.program;n.uniformBlockBinding(A,M)}function l(A,S){let M=r[A.id];M===void 0&&(_(A),M=d(A),r[A.id]=M,A.addEventListener("dispose",p));const C=S.program;n.updateUBOMapping(A,C);const R=e.render.frame;s[A.id]!==R&&(f(A),s[A.id]=R)}function d(A){const S=h();A.__bindingPointIndex=S;const M=i.createBuffer(),C=A.__size,R=A.usage;return i.bindBuffer(i.UNIFORM_BUFFER,M),i.bufferData(i.UNIFORM_BUFFER,C,R),i.bindBuffer(i.UNIFORM_BUFFER,null),i.bindBufferBase(i.UNIFORM_BUFFER,S,M),M}function h(){for(let A=0;A<a;A++)if(o.indexOf(A)===-1)return o.push(A),A;return console.error("THREE.WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached."),0}function f(A){const S=r[A.id],M=A.uniforms,C=A.__cache;i.bindBuffer(i.UNIFORM_BUFFER,S);for(let R=0,P=M.length;R<P;R++){const I=Array.isArray(M[R])?M[R]:[M[R]];for(let y=0,E=I.length;y<E;y++){const w=I[y];if(m(w,R,y,C)===!0){const Q=w.__offset,j=Array.isArray(w.value)?w.value:[w.value];let Z=0;for(let re=0;re<j.length;re++){const X=j[re],ae=v(X);typeof X=="number"||typeof X=="boolean"?(w.__data[0]=X,i.bufferSubData(i.UNIFORM_BUFFER,Q+Z,w.__data)):X.isMatrix3?(w.__data[0]=X.elements[0],w.__data[1]=X.elements[1],w.__data[2]=X.elements[2],w.__data[3]=0,w.__data[4]=X.elements[3],w.__data[5]=X.elements[4],w.__data[6]=X.elements[5],w.__data[7]=0,w.__data[8]=X.elements[6],w.__data[9]=X.elements[7],w.__data[10]=X.elements[8],w.__data[11]=0):(X.toArray(w.__data,Z),Z+=ae.storage/Float32Array.BYTES_PER_ELEMENT)}i.bufferSubData(i.UNIFORM_BUFFER,Q,w.__data)}}}i.bindBuffer(i.UNIFORM_BUFFER,null)}function m(A,S,M,C){const R=A.value,P=S+"_"+M;if(C[P]===void 0)return typeof R=="number"||typeof R=="boolean"?C[P]=R:C[P]=R.clone(),!0;{const I=C[P];if(typeof R=="number"||typeof R=="boolean"){if(I!==R)return C[P]=R,!0}else if(I.equals(R)===!1)return I.copy(R),!0}return!1}function _(A){const S=A.uniforms;let M=0;const C=16;for(let P=0,I=S.length;P<I;P++){const y=Array.isArray(S[P])?S[P]:[S[P]];for(let E=0,w=y.length;E<w;E++){const Q=y[E],j=Array.isArray(Q.value)?Q.value:[Q.value];for(let Z=0,re=j.length;Z<re;Z++){const X=j[Z],ae=v(X),W=M%C,he=W%ae.boundary,ye=W+he;M+=he,ye!==0&&C-ye<ae.storage&&(M+=C-ye),Q.__data=new Float32Array(ae.storage/Float32Array.BYTES_PER_ELEMENT),Q.__offset=M,M+=ae.storage}}}const R=M%C;return R>0&&(M+=C-R),A.__size=M,A.__cache={},this}function v(A){const S={boundary:0,storage:0};return typeof A=="number"||typeof A=="boolean"?(S.boundary=4,S.storage=4):A.isVector2?(S.boundary=8,S.storage=8):A.isVector3||A.isColor?(S.boundary=16,S.storage=12):A.isVector4?(S.boundary=16,S.storage=16):A.isMatrix3?(S.boundary=48,S.storage=48):A.isMatrix4?(S.boundary=64,S.storage=64):A.isTexture?console.warn("THREE.WebGLRenderer: Texture samplers can not be part of an uniforms group."):console.warn("THREE.WebGLRenderer: Unsupported uniform value type.",A),S}function p(A){const S=A.target;S.removeEventListener("dispose",p);const M=o.indexOf(S.__bindingPointIndex);o.splice(M,1),i.deleteBuffer(r[S.id]),delete r[S.id],delete s[S.id]}function c(){for(const A in r)i.deleteBuffer(r[A]);o=[],r={},s={}}return{bind:u,update:l,dispose:c}}class im{constructor(e={}){const{canvas:t=Rc(),context:n=null,depth:r=!0,stencil:s=!1,alpha:o=!1,antialias:a=!1,premultipliedAlpha:u=!0,preserveDrawingBuffer:l=!1,powerPreference:d="default",failIfMajorPerformanceCaveat:h=!1,reversedDepthBuffer:f=!1}=e;this.isWebGLRenderer=!0;let m;if(n!==null){if(typeof WebGLRenderingContext<"u"&&n instanceof WebGLRenderingContext)throw new Error("THREE.WebGLRenderer: WebGL 1 is not supported since r163.");m=n.getContextAttributes().alpha}else m=o;const _=new Uint32Array(4),v=new Int32Array(4);let p=null,c=null;const A=[],S=[];this.domElement=t,this.debug={checkShaderErrors:!0,onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this.toneMapping=kn,this.toneMappingExposure=1,this.transmissionResolutionScale=1;const M=this;let C=!1;this._outputColorSpace=Dt;let R=0,P=0,I=null,y=-1,E=null;const w=new Mt,Q=new Mt;let j=null;const Z=new je(0);let re=0,X=t.width,ae=t.height,W=1,he=null,ye=null;const Te=new Mt(0,0,X,ae),ze=new Mt(0,0,X,ae);let nt=!1;const it=new zo;let J=!1,L=!1;const D=new gt,z=new B,H=new Mt,G={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0};let Y=!1;function ee(){return I===null?W:1}let b=n;function ne(x,N){return t.getContext(x,N)}try{const x={alpha:!0,depth:r,stencil:s,antialias:a,premultipliedAlpha:u,preserveDrawingBuffer:l,powerPreference:d,failIfMajorPerformanceCaveat:h};if("setAttribute"in t&&t.setAttribute("data-engine",`three.js r${wo}`),t.addEventListener("webglcontextlost",ge,!1),t.addEventListener("webglcontextrestored",be,!1),t.addEventListener("webglcontextcreationerror",ce,!1),b===null){const N="webgl2";if(b=ne(N,x),b===null)throw ne(N)?new Error("Error creating WebGL context with your selected attributes."):new Error("Error creating WebGL context.")}}catch(x){throw console.error("THREE.WebGLRenderer: "+x.message),x}let q,me,K,Ke,ue,Ce,$e,Pe,T,g,O,te,se,$,ve,pe,we,Ue,de,xe,Ne,De,Me,We;function U(){q=new ff(b),q.init(),De=new Kp(b,q),me=new of(b,q,e,De),K=new Yp(b,q),me.reversedDepthBuffer&&f&&K.buffers.depth.setReversed(!0),Ke=new gf(b),ue=new Ip,Ce=new jp(b,q,K,ue,me,De,Ke),$e=new lf(M),Pe=new df(M),T=new Su(b),Me=new rf(b,T),g=new pf(b,T,Ke,Me),O=new vf(b,g,T,Ke),de=new _f(b,me,Ce),pe=new af(ue),te=new Up(M,$e,Pe,q,me,Me,pe),se=new tm(M,ue),$=new Fp,ve=new Vp(q),Ue=new nf(M,$e,Pe,K,O,m,u),we=new Xp(M,O,me),We=new nm(b,Ke,me,K),xe=new sf(b,q,Ke),Ne=new mf(b,q,Ke),Ke.programs=te.programs,M.capabilities=me,M.extensions=q,M.properties=ue,M.renderLists=$,M.shadowMap=we,M.state=K,M.info=Ke}U();const fe=new Qp(M,b);this.xr=fe,this.getContext=function(){return b},this.getContextAttributes=function(){return b.getContextAttributes()},this.forceContextLoss=function(){const x=q.get("WEBGL_lose_context");x&&x.loseContext()},this.forceContextRestore=function(){const x=q.get("WEBGL_lose_context");x&&x.restoreContext()},this.getPixelRatio=function(){return W},this.setPixelRatio=function(x){x!==void 0&&(W=x,this.setSize(X,ae,!1))},this.getSize=function(x){return x.set(X,ae)},this.setSize=function(x,N,k=!0){if(fe.isPresenting){console.warn("THREE.WebGLRenderer: Can't change size while VR device is presenting.");return}X=x,ae=N,t.width=Math.floor(x*W),t.height=Math.floor(N*W),k===!0&&(t.style.width=x+"px",t.style.height=N+"px"),this.setViewport(0,0,x,N)},this.getDrawingBufferSize=function(x){return x.set(X*W,ae*W).floor()},this.setDrawingBufferSize=function(x,N,k){X=x,ae=N,W=k,t.width=Math.floor(x*k),t.height=Math.floor(N*k),this.setViewport(0,0,x,N)},this.getCurrentViewport=function(x){return x.copy(w)},this.getViewport=function(x){return x.copy(Te)},this.setViewport=function(x,N,k,V){x.isVector4?Te.set(x.x,x.y,x.z,x.w):Te.set(x,N,k,V),K.viewport(w.copy(Te).multiplyScalar(W).round())},this.getScissor=function(x){return x.copy(ze)},this.setScissor=function(x,N,k,V){x.isVector4?ze.set(x.x,x.y,x.z,x.w):ze.set(x,N,k,V),K.scissor(Q.copy(ze).multiplyScalar(W).round())},this.getScissorTest=function(){return nt},this.setScissorTest=function(x){K.setScissorTest(nt=x)},this.setOpaqueSort=function(x){he=x},this.setTransparentSort=function(x){ye=x},this.getClearColor=function(x){return x.copy(Ue.getClearColor())},this.setClearColor=function(){Ue.setClearColor(...arguments)},this.getClearAlpha=function(){return Ue.getClearAlpha()},this.setClearAlpha=function(){Ue.setClearAlpha(...arguments)},this.clear=function(x=!0,N=!0,k=!0){let V=0;if(x){let F=!1;if(I!==null){const oe=I.texture.format;F=oe===Io||oe===Uo||oe===Lo}if(F){const oe=I.texture.type,_e=oe===_n||oe===ni||oe===er||oe===tr||oe===Po||oe===Do,Re=Ue.getClearColor(),Ae=Ue.getClearAlpha(),He=Re.r,ke=Re.g,Fe=Re.b;_e?(_[0]=He,_[1]=ke,_[2]=Fe,_[3]=Ae,b.clearBufferuiv(b.COLOR,0,_)):(v[0]=He,v[1]=ke,v[2]=Fe,v[3]=Ae,b.clearBufferiv(b.COLOR,0,v))}else V|=b.COLOR_BUFFER_BIT}N&&(V|=b.DEPTH_BUFFER_BIT),k&&(V|=b.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),b.clear(V)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.dispose=function(){t.removeEventListener("webglcontextlost",ge,!1),t.removeEventListener("webglcontextrestored",be,!1),t.removeEventListener("webglcontextcreationerror",ce,!1),Ue.dispose(),$.dispose(),ve.dispose(),ue.dispose(),$e.dispose(),Pe.dispose(),O.dispose(),Me.dispose(),We.dispose(),te.dispose(),fe.dispose(),fe.removeEventListener("sessionstart",Jt),fe.removeEventListener("sessionend",Hi),Qt.stop()};function ge(x){x.preventDefault(),console.log("THREE.WebGLRenderer: Context Lost."),C=!0}function be(){console.log("THREE.WebGLRenderer: Context Restored."),C=!1;const x=Ke.autoReset,N=we.enabled,k=we.autoUpdate,V=we.needsUpdate,F=we.type;U(),Ke.autoReset=x,we.enabled=N,we.autoUpdate=k,we.needsUpdate=V,we.type=F}function ce(x){console.error("THREE.WebGLRenderer: A WebGL context could not be created. Reason: ",x.statusMessage)}function ie(x){const N=x.target;N.removeEventListener("dispose",ie),Le(N)}function Le(x){Ve(x),ue.remove(x)}function Ve(x){const N=ue.get(x).programs;N!==void 0&&(N.forEach(function(k){te.releaseProgram(k)}),x.isShaderMaterial&&te.releaseShaderCache(x))}this.renderBufferDirect=function(x,N,k,V,F,oe){N===null&&(N=G);const _e=F.isMesh&&F.matrixWorld.determinant()<0,Re=ct(x,N,k,V,F);K.setMaterial(V,_e);let Ae=k.index,He=1;if(V.wireframe===!0){if(Ae=g.getWireframeAttribute(k),Ae===void 0)return;He=2}const ke=k.drawRange,Fe=k.attributes.position;let st=ke.start*He,ut=(ke.start+ke.count)*He;oe!==null&&(st=Math.max(st,oe.start*He),ut=Math.min(ut,(oe.start+oe.count)*He)),Ae!==null?(st=Math.max(st,0),ut=Math.min(ut,Ae.count)):Fe!=null&&(st=Math.max(st,0),ut=Math.min(ut,Fe.count));const xt=ut-st;if(xt<0||xt===1/0)return;Me.setup(F,V,Re,k,Ae);let pt,ft=xe;if(Ae!==null&&(pt=T.get(Ae),ft=Ne,ft.setIndex(pt)),F.isMesh)V.wireframe===!0?(K.setLineWidth(V.wireframeLinewidth*ee()),ft.setMode(b.LINES)):ft.setMode(b.TRIANGLES);else if(F.isLine){let Oe=V.linewidth;Oe===void 0&&(Oe=1),K.setLineWidth(Oe*ee()),F.isLineSegments?ft.setMode(b.LINES):F.isLineLoop?ft.setMode(b.LINE_LOOP):ft.setMode(b.LINE_STRIP)}else F.isPoints?ft.setMode(b.POINTS):F.isSprite&&ft.setMode(b.TRIANGLES);if(F.isBatchedMesh)if(F._multiDrawInstances!==null)Di("THREE.WebGLRenderer: renderMultiDrawInstances has been deprecated and will be removed in r184. Append to renderMultiDraw arguments and use indirection."),ft.renderMultiDrawInstances(F._multiDrawStarts,F._multiDrawCounts,F._multiDrawCount,F._multiDrawInstances);else if(q.get("WEBGL_multi_draw"))ft.renderMultiDraw(F._multiDrawStarts,F._multiDrawCounts,F._multiDrawCount);else{const Oe=F._multiDrawStarts,_t=F._multiDrawCounts,ot=F._multiDrawCount,Xt=Ae?T.get(Ae).bytesPerElement:1,ui=ue.get(V).currentProgram.getUniforms();for(let qt=0;qt<ot;qt++)ui.setValue(b,"_gl_DrawID",qt),ft.render(Oe[qt]/Xt,_t[qt])}else if(F.isInstancedMesh)ft.renderInstances(st,xt,F.count);else if(k.isInstancedBufferGeometry){const Oe=k._maxInstanceCount!==void 0?k._maxInstanceCount:1/0,_t=Math.min(k.instanceCount,Oe);ft.renderInstances(st,xt,_t)}else ft.render(st,xt)};function tt(x,N,k){x.transparent===!0&&x.side===An&&x.forceSinglePass===!1?(x.side=Wt,x.needsUpdate=!0,Ee(x,N,k),x.side=Vn,x.needsUpdate=!0,Ee(x,N,k),x.side=An):Ee(x,N,k)}this.compile=function(x,N,k=null){k===null&&(k=x),c=ve.get(k),c.init(N),S.push(c),k.traverseVisible(function(F){F.isLight&&F.layers.test(N.layers)&&(c.pushLight(F),F.castShadow&&c.pushShadow(F))}),x!==k&&x.traverseVisible(function(F){F.isLight&&F.layers.test(N.layers)&&(c.pushLight(F),F.castShadow&&c.pushShadow(F))}),c.setupLights();const V=new Set;return x.traverse(function(F){if(!(F.isMesh||F.isPoints||F.isLine||F.isSprite))return;const oe=F.material;if(oe)if(Array.isArray(oe))for(let _e=0;_e<oe.length;_e++){const Re=oe[_e];tt(Re,k,F),V.add(Re)}else tt(oe,k,F),V.add(oe)}),c=S.pop(),V},this.compileAsync=function(x,N,k=null){const V=this.compile(x,N,k);return new Promise(F=>{function oe(){if(V.forEach(function(_e){ue.get(_e).currentProgram.isReady()&&V.delete(_e)}),V.size===0){F(x);return}setTimeout(oe,10)}q.get("KHR_parallel_shader_compile")!==null?oe():setTimeout(oe,10)})};let Xe=null;function $t(x){Xe&&Xe(x)}function Jt(){Qt.stop()}function Hi(){Qt.start()}const Qt=new Al;Qt.setAnimationLoop($t),typeof self<"u"&&Qt.setContext(self),this.setAnimationLoop=function(x){Xe=x,fe.setAnimationLoop(x),x===null?Qt.stop():Qt.start()},fe.addEventListener("sessionstart",Jt),fe.addEventListener("sessionend",Hi),this.render=function(x,N){if(N!==void 0&&N.isCamera!==!0){console.error("THREE.WebGLRenderer.render: camera is not an instance of THREE.Camera.");return}if(C===!0)return;if(x.matrixWorldAutoUpdate===!0&&x.updateMatrixWorld(),N.parent===null&&N.matrixWorldAutoUpdate===!0&&N.updateMatrixWorld(),fe.enabled===!0&&fe.isPresenting===!0&&(fe.cameraAutoUpdate===!0&&fe.updateCamera(N),N=fe.getCamera()),x.isScene===!0&&x.onBeforeRender(M,x,N,I),c=ve.get(x,S.length),c.init(N),S.push(c),D.multiplyMatrices(N.projectionMatrix,N.matrixWorldInverse),it.setFromProjectionMatrix(D,gn,N.reversedDepth),L=this.localClippingEnabled,J=pe.init(this.clippingPlanes,L),p=$.get(x,A.length),p.init(),A.push(p),fe.enabled===!0&&fe.isPresenting===!0){const oe=M.xr.getDepthSensingMesh();oe!==null&&ai(oe,N,-1/0,M.sortObjects)}ai(x,N,0,M.sortObjects),p.finish(),M.sortObjects===!0&&p.sort(he,ye),Y=fe.enabled===!1||fe.isPresenting===!1||fe.hasDepthSensing()===!1,Y&&Ue.addToRenderList(p,x),this.info.render.frame++,J===!0&&pe.beginShadows();const k=c.state.shadowsArray;we.render(k,x,N),J===!0&&pe.endShadows(),this.info.autoReset===!0&&this.info.reset();const V=p.opaque,F=p.transmissive;if(c.setupLights(),N.isArrayCamera){const oe=N.cameras;if(F.length>0)for(let _e=0,Re=oe.length;_e<Re;_e++){const Ae=oe[_e];ki(V,F,x,Ae)}Y&&Ue.render(x);for(let _e=0,Re=oe.length;_e<Re;_e++){const Ae=oe[_e];li(p,x,Ae,Ae.viewport)}}else F.length>0&&ki(V,F,x,N),Y&&Ue.render(x),li(p,x,N);I!==null&&P===0&&(Ce.updateMultisampleRenderTarget(I),Ce.updateRenderTargetMipmap(I)),x.isScene===!0&&x.onAfterRender(M,x,N),Me.resetDefaultState(),y=-1,E=null,S.pop(),S.length>0?(c=S[S.length-1],J===!0&&pe.setGlobalState(M.clippingPlanes,c.state.camera)):c=null,A.pop(),A.length>0?p=A[A.length-1]:p=null};function ai(x,N,k,V){if(x.visible===!1)return;if(x.layers.test(N.layers)){if(x.isGroup)k=x.renderOrder;else if(x.isLOD)x.autoUpdate===!0&&x.update(N);else if(x.isLight)c.pushLight(x),x.castShadow&&c.pushShadow(x);else if(x.isSprite){if(!x.frustumCulled||it.intersectsSprite(x)){V&&H.setFromMatrixPosition(x.matrixWorld).applyMatrix4(D);const _e=O.update(x),Re=x.material;Re.visible&&p.push(x,_e,Re,k,H.z,null)}}else if((x.isMesh||x.isLine||x.isPoints)&&(!x.frustumCulled||it.intersectsObject(x))){const _e=O.update(x),Re=x.material;if(V&&(x.boundingSphere!==void 0?(x.boundingSphere===null&&x.computeBoundingSphere(),H.copy(x.boundingSphere.center)):(_e.boundingSphere===null&&_e.computeBoundingSphere(),H.copy(_e.boundingSphere.center)),H.applyMatrix4(x.matrixWorld).applyMatrix4(D)),Array.isArray(Re)){const Ae=_e.groups;for(let He=0,ke=Ae.length;He<ke;He++){const Fe=Ae[He],st=Re[Fe.materialIndex];st&&st.visible&&p.push(x,_e,st,k,H.z,Fe)}}else Re.visible&&p.push(x,_e,Re,k,H.z,null)}}const oe=x.children;for(let _e=0,Re=oe.length;_e<Re;_e++)ai(oe[_e],N,k,V)}function li(x,N,k,V){const F=x.opaque,oe=x.transmissive,_e=x.transparent;c.setupLightsView(k),J===!0&&pe.setGlobalState(M.clippingPlanes,k),V&&K.viewport(w.copy(V)),F.length>0&&ci(F,N,k),oe.length>0&&ci(oe,N,k),_e.length>0&&ci(_e,N,k),K.buffers.depth.setTest(!0),K.buffers.depth.setMask(!0),K.buffers.color.setMask(!0),K.setPolygonOffset(!1)}function ki(x,N,k,V){if((k.isScene===!0?k.overrideMaterial:null)!==null)return;c.state.transmissionRenderTarget[V.id]===void 0&&(c.state.transmissionRenderTarget[V.id]=new ri(1,1,{generateMipmaps:!0,type:q.has("EXT_color_buffer_half_float")||q.has("EXT_color_buffer_float")?or:_n,minFilter:Rn,samples:4,stencilBuffer:s,resolveDepthBuffer:!1,resolveStencilBuffer:!1,colorSpace:at.workingColorSpace}));const oe=c.state.transmissionRenderTarget[V.id],_e=V.viewport||w;oe.setSize(_e.z*M.transmissionResolutionScale,_e.w*M.transmissionResolutionScale);const Re=M.getRenderTarget(),Ae=M.getActiveCubeFace(),He=M.getActiveMipmapLevel();M.setRenderTarget(oe),M.getClearColor(Z),re=M.getClearAlpha(),re<1&&M.setClearColor(16777215,.5),M.clear(),Y&&Ue.render(k);const ke=M.toneMapping;M.toneMapping=kn;const Fe=V.viewport;if(V.viewport!==void 0&&(V.viewport=void 0),c.setupLightsView(V),J===!0&&pe.setGlobalState(M.clippingPlanes,V),ci(x,k,V),Ce.updateMultisampleRenderTarget(oe),Ce.updateRenderTargetMipmap(oe),q.has("WEBGL_multisampled_render_to_texture")===!1){let st=!1;for(let ut=0,xt=N.length;ut<xt;ut++){const pt=N[ut],ft=pt.object,Oe=pt.geometry,_t=pt.material,ot=pt.group;if(_t.side===An&&ft.layers.test(V.layers)){const Xt=_t.side;_t.side=Wt,_t.needsUpdate=!0,le(ft,k,V,Oe,_t,ot),_t.side=Xt,_t.needsUpdate=!0,st=!0}}st===!0&&(Ce.updateMultisampleRenderTarget(oe),Ce.updateRenderTargetMipmap(oe))}M.setRenderTarget(Re,Ae,He),M.setClearColor(Z,re),Fe!==void 0&&(V.viewport=Fe),M.toneMapping=ke}function ci(x,N,k){const V=N.isScene===!0?N.overrideMaterial:null;for(let F=0,oe=x.length;F<oe;F++){const _e=x[F],Re=_e.object,Ae=_e.geometry,He=_e.group;let ke=_e.material;ke.allowOverride===!0&&V!==null&&(ke=V),Re.layers.test(k.layers)&&le(Re,N,k,Ae,ke,He)}}function le(x,N,k,V,F,oe){x.onBeforeRender(M,N,k,V,F,oe),x.modelViewMatrix.multiplyMatrices(k.matrixWorldInverse,x.matrixWorld),x.normalMatrix.getNormalMatrix(x.modelViewMatrix),F.onBeforeRender(M,N,k,V,x,oe),F.transparent===!0&&F.side===An&&F.forceSinglePass===!1?(F.side=Wt,F.needsUpdate=!0,M.renderBufferDirect(k,N,V,F,x,oe),F.side=Vn,F.needsUpdate=!0,M.renderBufferDirect(k,N,V,F,x,oe),F.side=An):M.renderBufferDirect(k,N,V,F,x,oe),x.onAfterRender(M,N,k,V,F,oe)}function Ee(x,N,k){N.isScene!==!0&&(N=G);const V=ue.get(x),F=c.state.lights,oe=c.state.shadowsArray,_e=F.state.version,Re=te.getParameters(x,F.state,oe,N,k),Ae=te.getProgramCacheKey(Re);let He=V.programs;V.environment=x.isMeshStandardMaterial?N.environment:null,V.fog=N.fog,V.envMap=(x.isMeshStandardMaterial?Pe:$e).get(x.envMap||V.environment),V.envMapRotation=V.environment!==null&&x.envMap===null?N.environmentRotation:x.envMapRotation,He===void 0&&(x.addEventListener("dispose",ie),He=new Map,V.programs=He);let ke=He.get(Ae);if(ke!==void 0){if(V.currentProgram===ke&&V.lightsStateVersion===_e)return Ge(x,Re),ke}else Re.uniforms=te.getUniforms(x),x.onBeforeCompile(Re,M),ke=te.acquireProgram(Re,Ae),He.set(Ae,ke),V.uniforms=Re.uniforms;const Fe=V.uniforms;return(!x.isShaderMaterial&&!x.isRawShaderMaterial||x.clipping===!0)&&(Fe.clippingPlanes=pe.uniform),Ge(x,Re),V.needsLights=qe(x),V.lightsStateVersion=_e,V.needsLights&&(Fe.ambientLightColor.value=F.state.ambient,Fe.lightProbe.value=F.state.probe,Fe.directionalLights.value=F.state.directional,Fe.directionalLightShadows.value=F.state.directionalShadow,Fe.spotLights.value=F.state.spot,Fe.spotLightShadows.value=F.state.spotShadow,Fe.rectAreaLights.value=F.state.rectArea,Fe.ltc_1.value=F.state.rectAreaLTC1,Fe.ltc_2.value=F.state.rectAreaLTC2,Fe.pointLights.value=F.state.point,Fe.pointLightShadows.value=F.state.pointShadow,Fe.hemisphereLights.value=F.state.hemi,Fe.directionalShadowMap.value=F.state.directionalShadowMap,Fe.directionalShadowMatrix.value=F.state.directionalShadowMatrix,Fe.spotShadowMap.value=F.state.spotShadowMap,Fe.spotLightMatrix.value=F.state.spotLightMatrix,Fe.spotLightMap.value=F.state.spotLightMap,Fe.pointShadowMap.value=F.state.pointShadowMap,Fe.pointShadowMatrix.value=F.state.pointShadowMatrix),V.currentProgram=ke,V.uniformsList=null,ke}function Be(x){if(x.uniformsList===null){const N=x.currentProgram.getUniforms();x.uniformsList=Gr.seqWithValue(N.seq,x.uniforms)}return x.uniformsList}function Ge(x,N){const k=ue.get(x);k.outputColorSpace=N.outputColorSpace,k.batching=N.batching,k.batchingColor=N.batchingColor,k.instancing=N.instancing,k.instancingColor=N.instancingColor,k.instancingMorph=N.instancingMorph,k.skinning=N.skinning,k.morphTargets=N.morphTargets,k.morphNormals=N.morphNormals,k.morphColors=N.morphColors,k.morphTargetsCount=N.morphTargetsCount,k.numClippingPlanes=N.numClippingPlanes,k.numIntersection=N.numClipIntersection,k.vertexAlphas=N.vertexAlphas,k.vertexTangents=N.vertexTangents,k.toneMapping=N.toneMapping}function ct(x,N,k,V,F){N.isScene!==!0&&(N=G),Ce.resetTextureUnits();const oe=N.fog,_e=V.isMeshStandardMaterial?N.environment:null,Re=I===null?M.outputColorSpace:I.isXRRenderTarget===!0?I.texture.colorSpace:Fi,Ae=(V.isMeshStandardMaterial?Pe:$e).get(V.envMap||_e),He=V.vertexColors===!0&&!!k.attributes.color&&k.attributes.color.itemSize===4,ke=!!k.attributes.tangent&&(!!V.normalMap||V.anisotropy>0),Fe=!!k.morphAttributes.position,st=!!k.morphAttributes.normal,ut=!!k.morphAttributes.color;let xt=kn;V.toneMapped&&(I===null||I.isXRRenderTarget===!0)&&(xt=M.toneMapping);const pt=k.morphAttributes.position||k.morphAttributes.normal||k.morphAttributes.color,ft=pt!==void 0?pt.length:0,Oe=ue.get(V),_t=c.state.lights;if(J===!0&&(L===!0||x!==E)){const It=x===E&&V.id===y;pe.setState(V,x,It)}let ot=!1;V.version===Oe.__version?(Oe.needsLights&&Oe.lightsStateVersion!==_t.state.version||Oe.outputColorSpace!==Re||F.isBatchedMesh&&Oe.batching===!1||!F.isBatchedMesh&&Oe.batching===!0||F.isBatchedMesh&&Oe.batchingColor===!0&&F.colorTexture===null||F.isBatchedMesh&&Oe.batchingColor===!1&&F.colorTexture!==null||F.isInstancedMesh&&Oe.instancing===!1||!F.isInstancedMesh&&Oe.instancing===!0||F.isSkinnedMesh&&Oe.skinning===!1||!F.isSkinnedMesh&&Oe.skinning===!0||F.isInstancedMesh&&Oe.instancingColor===!0&&F.instanceColor===null||F.isInstancedMesh&&Oe.instancingColor===!1&&F.instanceColor!==null||F.isInstancedMesh&&Oe.instancingMorph===!0&&F.morphTexture===null||F.isInstancedMesh&&Oe.instancingMorph===!1&&F.morphTexture!==null||Oe.envMap!==Ae||V.fog===!0&&Oe.fog!==oe||Oe.numClippingPlanes!==void 0&&(Oe.numClippingPlanes!==pe.numPlanes||Oe.numIntersection!==pe.numIntersection)||Oe.vertexAlphas!==He||Oe.vertexTangents!==ke||Oe.morphTargets!==Fe||Oe.morphNormals!==st||Oe.morphColors!==ut||Oe.toneMapping!==xt||Oe.morphTargetsCount!==ft)&&(ot=!0):(ot=!0,Oe.__version=V.version);let Xt=Oe.currentProgram;ot===!0&&(Xt=Ee(V,N,F));let ui=!1,qt=!1,Vi=!1;const vt=Xt.getUniforms(),en=Oe.uniforms;if(K.useProgram(Xt.program)&&(ui=!0,qt=!0,Vi=!0),V.id!==y&&(y=V.id,qt=!0),ui||E!==x){K.buffers.depth.getReversed()&&x.reversedDepth!==!0&&(x._reversedDepth=!0,x.updateProjectionMatrix()),vt.setValue(b,"projectionMatrix",x.projectionMatrix),vt.setValue(b,"viewMatrix",x.matrixWorldInverse);const zt=vt.map.cameraPosition;zt!==void 0&&zt.setValue(b,z.setFromMatrixPosition(x.matrixWorld)),me.logarithmicDepthBuffer&&vt.setValue(b,"logDepthBufFC",2/(Math.log(x.far+1)/Math.LN2)),(V.isMeshPhongMaterial||V.isMeshToonMaterial||V.isMeshLambertMaterial||V.isMeshBasicMaterial||V.isMeshStandardMaterial||V.isShaderMaterial)&&vt.setValue(b,"isOrthographic",x.isOrthographicCamera===!0),E!==x&&(E=x,qt=!0,Vi=!0)}if(F.isSkinnedMesh){vt.setOptional(b,F,"bindMatrix"),vt.setOptional(b,F,"bindMatrixInverse");const It=F.skeleton;It&&(It.boneTexture===null&&It.computeBoneTexture(),vt.setValue(b,"boneTexture",It.boneTexture,Ce))}F.isBatchedMesh&&(vt.setOptional(b,F,"batchingTexture"),vt.setValue(b,"batchingTexture",F._matricesTexture,Ce),vt.setOptional(b,F,"batchingIdTexture"),vt.setValue(b,"batchingIdTexture",F._indirectTexture,Ce),vt.setOptional(b,F,"batchingColorTexture"),F._colorsTexture!==null&&vt.setValue(b,"batchingColorTexture",F._colorsTexture,Ce));const tn=k.morphAttributes;if((tn.position!==void 0||tn.normal!==void 0||tn.color!==void 0)&&de.update(F,k,Xt),(qt||Oe.receiveShadow!==F.receiveShadow)&&(Oe.receiveShadow=F.receiveShadow,vt.setValue(b,"receiveShadow",F.receiveShadow)),V.isMeshGouraudMaterial&&V.envMap!==null&&(en.envMap.value=Ae,en.flipEnvMap.value=Ae.isCubeTexture&&Ae.isRenderTargetTexture===!1?-1:1),V.isMeshStandardMaterial&&V.envMap===null&&N.environment!==null&&(en.envMapIntensity.value=N.environmentIntensity),qt&&(vt.setValue(b,"toneMappingExposure",M.toneMappingExposure),Oe.needsLights&&Je(en,Vi),oe&&V.fog===!0&&se.refreshFogUniforms(en,oe),se.refreshMaterialUniforms(en,V,W,ae,c.state.transmissionRenderTarget[x.id]),Gr.upload(b,Be(Oe),en,Ce)),V.isShaderMaterial&&V.uniformsNeedUpdate===!0&&(Gr.upload(b,Be(Oe),en,Ce),V.uniformsNeedUpdate=!1),V.isSpriteMaterial&&vt.setValue(b,"center",F.center),vt.setValue(b,"modelViewMatrix",F.modelViewMatrix),vt.setValue(b,"normalMatrix",F.normalMatrix),vt.setValue(b,"modelMatrix",F.matrixWorld),V.isShaderMaterial||V.isRawShaderMaterial){const It=V.uniformsGroups;for(let zt=0,Qr=It.length;zt<Qr;zt++){const Xn=It[zt];We.update(Xn,Xt),We.bind(Xn,Xt)}}return Xt}function Je(x,N){x.ambientLightColor.needsUpdate=N,x.lightProbe.needsUpdate=N,x.directionalLights.needsUpdate=N,x.directionalLightShadows.needsUpdate=N,x.pointLights.needsUpdate=N,x.pointLightShadows.needsUpdate=N,x.spotLights.needsUpdate=N,x.spotLightShadows.needsUpdate=N,x.rectAreaLights.needsUpdate=N,x.hemisphereLights.needsUpdate=N}function qe(x){return x.isMeshLambertMaterial||x.isMeshToonMaterial||x.isMeshPhongMaterial||x.isMeshStandardMaterial||x.isShadowMaterial||x.isShaderMaterial&&x.lights===!0}this.getActiveCubeFace=function(){return R},this.getActiveMipmapLevel=function(){return P},this.getRenderTarget=function(){return I},this.setRenderTargetTextures=function(x,N,k){const V=ue.get(x);V.__autoAllocateDepthBuffer=x.resolveDepthBuffer===!1,V.__autoAllocateDepthBuffer===!1&&(V.__useRenderToTexture=!1),ue.get(x.texture).__webglTexture=N,ue.get(x.depthTexture).__webglTexture=V.__autoAllocateDepthBuffer?void 0:k,V.__hasExternalTextures=!0},this.setRenderTargetFramebuffer=function(x,N){const k=ue.get(x);k.__webglFramebuffer=N,k.__useDefaultFramebuffer=N===void 0};const Et=b.createFramebuffer();this.setRenderTarget=function(x,N=0,k=0){I=x,R=N,P=k;let V=!0,F=null,oe=!1,_e=!1;if(x){const Ae=ue.get(x);if(Ae.__useDefaultFramebuffer!==void 0)K.bindFramebuffer(b.FRAMEBUFFER,null),V=!1;else if(Ae.__webglFramebuffer===void 0)Ce.setupRenderTarget(x);else if(Ae.__hasExternalTextures)Ce.rebindTextures(x,ue.get(x.texture).__webglTexture,ue.get(x.depthTexture).__webglTexture);else if(x.depthBuffer){const Fe=x.depthTexture;if(Ae.__boundDepthTexture!==Fe){if(Fe!==null&&ue.has(Fe)&&(x.width!==Fe.image.width||x.height!==Fe.image.height))throw new Error("WebGLRenderTarget: Attached DepthTexture is initialized to the incorrect size.");Ce.setupDepthRenderbuffer(x)}}const He=x.texture;(He.isData3DTexture||He.isDataArrayTexture||He.isCompressedArrayTexture)&&(_e=!0);const ke=ue.get(x).__webglFramebuffer;x.isWebGLCubeRenderTarget?(Array.isArray(ke[N])?F=ke[N][k]:F=ke[N],oe=!0):x.samples>0&&Ce.useMultisampledRTT(x)===!1?F=ue.get(x).__webglMultisampledFramebuffer:Array.isArray(ke)?F=ke[k]:F=ke,w.copy(x.viewport),Q.copy(x.scissor),j=x.scissorTest}else w.copy(Te).multiplyScalar(W).floor(),Q.copy(ze).multiplyScalar(W).floor(),j=nt;if(k!==0&&(F=Et),K.bindFramebuffer(b.FRAMEBUFFER,F)&&V&&K.drawBuffers(x,F),K.viewport(w),K.scissor(Q),K.setScissorTest(j),oe){const Ae=ue.get(x.texture);b.framebufferTexture2D(b.FRAMEBUFFER,b.COLOR_ATTACHMENT0,b.TEXTURE_CUBE_MAP_POSITIVE_X+N,Ae.__webglTexture,k)}else if(_e){const Ae=N;for(let He=0;He<x.textures.length;He++){const ke=ue.get(x.textures[He]);b.framebufferTextureLayer(b.FRAMEBUFFER,b.COLOR_ATTACHMENT0+He,ke.__webglTexture,k,Ae)}}else if(x!==null&&k!==0){const Ae=ue.get(x.texture);b.framebufferTexture2D(b.FRAMEBUFFER,b.COLOR_ATTACHMENT0,b.TEXTURE_2D,Ae.__webglTexture,k)}y=-1},this.readRenderTargetPixels=function(x,N,k,V,F,oe,_e,Re=0){if(!(x&&x.isWebGLRenderTarget)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");return}let Ae=ue.get(x).__webglFramebuffer;if(x.isWebGLCubeRenderTarget&&_e!==void 0&&(Ae=Ae[_e]),Ae){K.bindFramebuffer(b.FRAMEBUFFER,Ae);try{const He=x.textures[Re],ke=He.format,Fe=He.type;if(!me.textureFormatReadable(ke)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.");return}if(!me.textureTypeReadable(Fe)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.");return}N>=0&&N<=x.width-V&&k>=0&&k<=x.height-F&&(x.textures.length>1&&b.readBuffer(b.COLOR_ATTACHMENT0+Re),b.readPixels(N,k,V,F,De.convert(ke),De.convert(Fe),oe))}finally{const He=I!==null?ue.get(I).__webglFramebuffer:null;K.bindFramebuffer(b.FRAMEBUFFER,He)}}},this.readRenderTargetPixelsAsync=async function(x,N,k,V,F,oe,_e,Re=0){if(!(x&&x.isWebGLRenderTarget))throw new Error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");let Ae=ue.get(x).__webglFramebuffer;if(x.isWebGLCubeRenderTarget&&_e!==void 0&&(Ae=Ae[_e]),Ae)if(N>=0&&N<=x.width-V&&k>=0&&k<=x.height-F){K.bindFramebuffer(b.FRAMEBUFFER,Ae);const He=x.textures[Re],ke=He.format,Fe=He.type;if(!me.textureFormatReadable(ke))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.");if(!me.textureTypeReadable(Fe))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.");const st=b.createBuffer();b.bindBuffer(b.PIXEL_PACK_BUFFER,st),b.bufferData(b.PIXEL_PACK_BUFFER,oe.byteLength,b.STREAM_READ),x.textures.length>1&&b.readBuffer(b.COLOR_ATTACHMENT0+Re),b.readPixels(N,k,V,F,De.convert(ke),De.convert(Fe),0);const ut=I!==null?ue.get(I).__webglFramebuffer:null;K.bindFramebuffer(b.FRAMEBUFFER,ut);const xt=b.fenceSync(b.SYNC_GPU_COMMANDS_COMPLETE,0);return b.flush(),await Cc(b,xt,4),b.bindBuffer(b.PIXEL_PACK_BUFFER,st),b.getBufferSubData(b.PIXEL_PACK_BUFFER,0,oe),b.deleteBuffer(st),b.deleteSync(xt),oe}else throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.")},this.copyFramebufferToTexture=function(x,N=null,k=0){const V=Math.pow(2,-k),F=Math.floor(x.image.width*V),oe=Math.floor(x.image.height*V),_e=N!==null?N.x:0,Re=N!==null?N.y:0;Ce.setTexture2D(x,0),b.copyTexSubImage2D(b.TEXTURE_2D,k,0,0,_e,Re,F,oe),K.unbindTexture()};const Tt=b.createFramebuffer(),Rt=b.createFramebuffer();this.copyTextureToTexture=function(x,N,k=null,V=null,F=0,oe=null){oe===null&&(F!==0?(Di("WebGLRenderer: copyTextureToTexture function signature has changed to support src and dst mipmap levels."),oe=F,F=0):oe=0);let _e,Re,Ae,He,ke,Fe,st,ut,xt;const pt=x.isCompressedTexture?x.mipmaps[oe]:x.image;if(k!==null)_e=k.max.x-k.min.x,Re=k.max.y-k.min.y,Ae=k.isBox3?k.max.z-k.min.z:1,He=k.min.x,ke=k.min.y,Fe=k.isBox3?k.min.z:0;else{const tn=Math.pow(2,-F);_e=Math.floor(pt.width*tn),Re=Math.floor(pt.height*tn),x.isDataArrayTexture?Ae=pt.depth:x.isData3DTexture?Ae=Math.floor(pt.depth*tn):Ae=1,He=0,ke=0,Fe=0}V!==null?(st=V.x,ut=V.y,xt=V.z):(st=0,ut=0,xt=0);const ft=De.convert(N.format),Oe=De.convert(N.type);let _t;N.isData3DTexture?(Ce.setTexture3D(N,0),_t=b.TEXTURE_3D):N.isDataArrayTexture||N.isCompressedArrayTexture?(Ce.setTexture2DArray(N,0),_t=b.TEXTURE_2D_ARRAY):(Ce.setTexture2D(N,0),_t=b.TEXTURE_2D),b.pixelStorei(b.UNPACK_FLIP_Y_WEBGL,N.flipY),b.pixelStorei(b.UNPACK_PREMULTIPLY_ALPHA_WEBGL,N.premultiplyAlpha),b.pixelStorei(b.UNPACK_ALIGNMENT,N.unpackAlignment);const ot=b.getParameter(b.UNPACK_ROW_LENGTH),Xt=b.getParameter(b.UNPACK_IMAGE_HEIGHT),ui=b.getParameter(b.UNPACK_SKIP_PIXELS),qt=b.getParameter(b.UNPACK_SKIP_ROWS),Vi=b.getParameter(b.UNPACK_SKIP_IMAGES);b.pixelStorei(b.UNPACK_ROW_LENGTH,pt.width),b.pixelStorei(b.UNPACK_IMAGE_HEIGHT,pt.height),b.pixelStorei(b.UNPACK_SKIP_PIXELS,He),b.pixelStorei(b.UNPACK_SKIP_ROWS,ke),b.pixelStorei(b.UNPACK_SKIP_IMAGES,Fe);const vt=x.isDataArrayTexture||x.isData3DTexture,en=N.isDataArrayTexture||N.isData3DTexture;if(x.isDepthTexture){const tn=ue.get(x),It=ue.get(N),zt=ue.get(tn.__renderTarget),Qr=ue.get(It.__renderTarget);K.bindFramebuffer(b.READ_FRAMEBUFFER,zt.__webglFramebuffer),K.bindFramebuffer(b.DRAW_FRAMEBUFFER,Qr.__webglFramebuffer);for(let Xn=0;Xn<Ae;Xn++)vt&&(b.framebufferTextureLayer(b.READ_FRAMEBUFFER,b.COLOR_ATTACHMENT0,ue.get(x).__webglTexture,F,Fe+Xn),b.framebufferTextureLayer(b.DRAW_FRAMEBUFFER,b.COLOR_ATTACHMENT0,ue.get(N).__webglTexture,oe,xt+Xn)),b.blitFramebuffer(He,ke,_e,Re,st,ut,_e,Re,b.DEPTH_BUFFER_BIT,b.NEAREST);K.bindFramebuffer(b.READ_FRAMEBUFFER,null),K.bindFramebuffer(b.DRAW_FRAMEBUFFER,null)}else if(F!==0||x.isRenderTargetTexture||ue.has(x)){const tn=ue.get(x),It=ue.get(N);K.bindFramebuffer(b.READ_FRAMEBUFFER,Tt),K.bindFramebuffer(b.DRAW_FRAMEBUFFER,Rt);for(let zt=0;zt<Ae;zt++)vt?b.framebufferTextureLayer(b.READ_FRAMEBUFFER,b.COLOR_ATTACHMENT0,tn.__webglTexture,F,Fe+zt):b.framebufferTexture2D(b.READ_FRAMEBUFFER,b.COLOR_ATTACHMENT0,b.TEXTURE_2D,tn.__webglTexture,F),en?b.framebufferTextureLayer(b.DRAW_FRAMEBUFFER,b.COLOR_ATTACHMENT0,It.__webglTexture,oe,xt+zt):b.framebufferTexture2D(b.DRAW_FRAMEBUFFER,b.COLOR_ATTACHMENT0,b.TEXTURE_2D,It.__webglTexture,oe),F!==0?b.blitFramebuffer(He,ke,_e,Re,st,ut,_e,Re,b.COLOR_BUFFER_BIT,b.NEAREST):en?b.copyTexSubImage3D(_t,oe,st,ut,xt+zt,He,ke,_e,Re):b.copyTexSubImage2D(_t,oe,st,ut,He,ke,_e,Re);K.bindFramebuffer(b.READ_FRAMEBUFFER,null),K.bindFramebuffer(b.DRAW_FRAMEBUFFER,null)}else en?x.isDataTexture||x.isData3DTexture?b.texSubImage3D(_t,oe,st,ut,xt,_e,Re,Ae,ft,Oe,pt.data):N.isCompressedArrayTexture?b.compressedTexSubImage3D(_t,oe,st,ut,xt,_e,Re,Ae,ft,pt.data):b.texSubImage3D(_t,oe,st,ut,xt,_e,Re,Ae,ft,Oe,pt):x.isDataTexture?b.texSubImage2D(b.TEXTURE_2D,oe,st,ut,_e,Re,ft,Oe,pt.data):x.isCompressedTexture?b.compressedTexSubImage2D(b.TEXTURE_2D,oe,st,ut,pt.width,pt.height,ft,pt.data):b.texSubImage2D(b.TEXTURE_2D,oe,st,ut,_e,Re,ft,Oe,pt);b.pixelStorei(b.UNPACK_ROW_LENGTH,ot),b.pixelStorei(b.UNPACK_IMAGE_HEIGHT,Xt),b.pixelStorei(b.UNPACK_SKIP_PIXELS,ui),b.pixelStorei(b.UNPACK_SKIP_ROWS,qt),b.pixelStorei(b.UNPACK_SKIP_IMAGES,Vi),oe===0&&N.generateMipmaps&&b.generateMipmap(_t),K.unbindTexture()},this.copyTextureToTexture3D=function(x,N,k=null,V=null,F=0){return Di('WebGLRenderer: copyTextureToTexture3D function has been deprecated. Use "copyTextureToTexture" instead.'),this.copyTextureToTexture(x,N,k,V,F)},this.initRenderTarget=function(x){ue.get(x).__webglFramebuffer===void 0&&Ce.setupRenderTarget(x)},this.initTexture=function(x){x.isCubeTexture?Ce.setTextureCube(x,0):x.isData3DTexture?Ce.setTexture3D(x,0):x.isDataArrayTexture||x.isCompressedArrayTexture?Ce.setTexture2DArray(x,0):Ce.setTexture2D(x,0),K.unbindTexture()},this.resetState=function(){R=0,P=0,I=null,K.reset(),Me.reset()},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}get coordinateSystem(){return gn}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(e){this._outputColorSpace=e;const t=this.getContext();t.drawingBufferColorSpace=at._getDrawingBufferColorSpace(e),t.unpackColorSpace=at._getUnpackColorSpace()}}const $a={type:"change"},Wo={type:"start"},Ll={type:"end"},Or=new Zr,Ja=new bn,rm=Math.cos(70*wc.DEG2RAD),bt=new B,kt=2*Math.PI,dt={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},Us=1e-6;class sm extends xu{constructor(e,t=null){super(e,t),this.state=dt.NONE,this.target=new B,this.cursor=new B,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.keyRotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:Ci.ROTATE,MIDDLE:Ci.DOLLY,RIGHT:Ci.PAN},this.touches={ONE:Ai.ROTATE,TWO:Ai.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._domElementKeyEvents=null,this._lastPosition=new B,this._lastQuaternion=new ii,this._lastTargetPosition=new B,this._quat=new ii().setFromUnitVectors(e.up,new B(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new ba,this._sphericalDelta=new ba,this._scale=1,this._panOffset=new B,this._rotateStart=new Ye,this._rotateEnd=new Ye,this._rotateDelta=new Ye,this._panStart=new Ye,this._panEnd=new Ye,this._panDelta=new Ye,this._dollyStart=new Ye,this._dollyEnd=new Ye,this._dollyDelta=new Ye,this._dollyDirection=new B,this._mouse=new Ye,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=am.bind(this),this._onPointerDown=om.bind(this),this._onPointerUp=lm.bind(this),this._onContextMenu=mm.bind(this),this._onMouseWheel=hm.bind(this),this._onKeyDown=dm.bind(this),this._onTouchStart=fm.bind(this),this._onTouchMove=pm.bind(this),this._onMouseDown=cm.bind(this),this._onMouseMove=um.bind(this),this._interceptControlDown=gm.bind(this),this._interceptControlUp=_m.bind(this),this.domElement!==null&&this.connect(this.domElement),this.update()}connect(e){super.connect(e),this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents(),this.domElement.getRootNode().removeEventListener("keydown",this._interceptControlDown,{capture:!0}),this.domElement.style.touchAction="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(e){e.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=e}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent($a),this.update(),this.state=dt.NONE}update(e=null){const t=this.object.position;bt.copy(t).sub(this.target),bt.applyQuaternion(this._quat),this._spherical.setFromVector3(bt),this.autoRotate&&this.state===dt.NONE&&this._rotateLeft(this._getAutoRotationAngle(e)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,r=this.maxAzimuthAngle;isFinite(n)&&isFinite(r)&&(n<-Math.PI?n+=kt:n>Math.PI&&(n-=kt),r<-Math.PI?r+=kt:r>Math.PI&&(r-=kt),n<=r?this._spherical.theta=Math.max(n,Math.min(r,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+r)/2?Math.max(n,this._spherical.theta):Math.min(r,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let s=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{const o=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),s=o!=this._spherical.radius}if(bt.setFromSpherical(this._spherical),bt.applyQuaternion(this._quatInverse),t.copy(this.target).add(bt),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let o=null;if(this.object.isPerspectiveCamera){const a=bt.length();o=this._clampDistance(a*this._scale);const u=a-o;this.object.position.addScaledVector(this._dollyDirection,u),this.object.updateMatrixWorld(),s=!!u}else if(this.object.isOrthographicCamera){const a=new B(this._mouse.x,this._mouse.y,0);a.unproject(this.object);const u=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),s=u!==this.object.zoom;const l=new B(this._mouse.x,this._mouse.y,0);l.unproject(this.object),this.object.position.sub(l).add(a),this.object.updateMatrixWorld(),o=bt.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;o!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(o).add(this.object.position):(Or.origin.copy(this.object.position),Or.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(Or.direction))<rm?this.object.lookAt(this.target):(Ja.setFromNormalAndCoplanarPoint(this.object.up,this.target),Or.intersectPlane(Ja,this.target))))}else if(this.object.isOrthographicCamera){const o=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),o!==this.object.zoom&&(this.object.updateProjectionMatrix(),s=!0)}return this._scale=1,this._performCursorZoom=!1,s||this._lastPosition.distanceToSquared(this.object.position)>Us||8*(1-this._lastQuaternion.dot(this.object.quaternion))>Us||this._lastTargetPosition.distanceToSquared(this.target)>Us?(this.dispatchEvent($a),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(e){return e!==null?kt/60*this.autoRotateSpeed*e:kt/60/60*this.autoRotateSpeed}_getZoomScale(e){const t=Math.abs(e*.01);return Math.pow(.95,this.zoomSpeed*t)}_rotateLeft(e){this._sphericalDelta.theta-=e}_rotateUp(e){this._sphericalDelta.phi-=e}_panLeft(e,t){bt.setFromMatrixColumn(t,0),bt.multiplyScalar(-e),this._panOffset.add(bt)}_panUp(e,t){this.screenSpacePanning===!0?bt.setFromMatrixColumn(t,1):(bt.setFromMatrixColumn(t,0),bt.crossVectors(this.object.up,bt)),bt.multiplyScalar(e),this._panOffset.add(bt)}_pan(e,t){const n=this.domElement;if(this.object.isPerspectiveCamera){const r=this.object.position;bt.copy(r).sub(this.target);let s=bt.length();s*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*e*s/n.clientHeight,this.object.matrix),this._panUp(2*t*s/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(e*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(t*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(e,t){if(!this.zoomToCursor)return;this._performCursorZoom=!0;const n=this.domElement.getBoundingClientRect(),r=e-n.left,s=t-n.top,o=n.width,a=n.height;this._mouse.x=r/o*2-1,this._mouse.y=-(s/a)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(e){return Math.max(this.minDistance,Math.min(this.maxDistance,e))}_handleMouseDownRotate(e){this._rotateStart.set(e.clientX,e.clientY)}_handleMouseDownDolly(e){this._updateZoomParameters(e.clientX,e.clientX),this._dollyStart.set(e.clientX,e.clientY)}_handleMouseDownPan(e){this._panStart.set(e.clientX,e.clientY)}_handleMouseMoveRotate(e){this._rotateEnd.set(e.clientX,e.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const t=this.domElement;this._rotateLeft(kt*this._rotateDelta.x/t.clientHeight),this._rotateUp(kt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(e){this._dollyEnd.set(e.clientX,e.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(e){this._panEnd.set(e.clientX,e.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(e){this._updateZoomParameters(e.clientX,e.clientY),e.deltaY<0?this._dollyIn(this._getZoomScale(e.deltaY)):e.deltaY>0&&this._dollyOut(this._getZoomScale(e.deltaY)),this.update()}_handleKeyDown(e){let t=!1;switch(e.code){case this.keys.UP:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),t=!0;break;case this.keys.BOTTOM:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(-kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),t=!0;break;case this.keys.LEFT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),t=!0;break;case this.keys.RIGHT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(-kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),t=!0;break}t&&(e.preventDefault(),this.update())}_handleTouchStartRotate(e){if(this._pointers.length===1)this._rotateStart.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._rotateStart.set(n,r)}}_handleTouchStartPan(e){if(this._pointers.length===1)this._panStart.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panStart.set(n,r)}}_handleTouchStartDolly(e){const t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,s=Math.sqrt(n*n+r*r);this._dollyStart.set(0,s)}_handleTouchStartDollyPan(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enablePan&&this._handleTouchStartPan(e)}_handleTouchStartDollyRotate(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enableRotate&&this._handleTouchStartRotate(e)}_handleTouchMoveRotate(e){if(this._pointers.length==1)this._rotateEnd.set(e.pageX,e.pageY);else{const n=this._getSecondPointerPosition(e),r=.5*(e.pageX+n.x),s=.5*(e.pageY+n.y);this._rotateEnd.set(r,s)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const t=this.domElement;this._rotateLeft(kt*this._rotateDelta.x/t.clientHeight),this._rotateUp(kt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(e){if(this._pointers.length===1)this._panEnd.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panEnd.set(n,r)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(e){const t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,s=Math.sqrt(n*n+r*r);this._dollyEnd.set(0,s),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);const o=(e.pageX+t.x)*.5,a=(e.pageY+t.y)*.5;this._updateZoomParameters(o,a)}_handleTouchMoveDollyPan(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enablePan&&this._handleTouchMovePan(e)}_handleTouchMoveDollyRotate(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enableRotate&&this._handleTouchMoveRotate(e)}_addPointer(e){this._pointers.push(e.pointerId)}_removePointer(e){delete this._pointerPositions[e.pointerId];for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId){this._pointers.splice(t,1);return}}_isTrackingPointer(e){for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId)return!0;return!1}_trackPointer(e){let t=this._pointerPositions[e.pointerId];t===void 0&&(t=new Ye,this._pointerPositions[e.pointerId]=t),t.set(e.pageX,e.pageY)}_getSecondPointerPosition(e){const t=e.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[t]}_customWheelEvent(e){const t=e.deltaMode,n={clientX:e.clientX,clientY:e.clientY,deltaY:e.deltaY};switch(t){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return e.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}}function om(i){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(i.pointerId),this.domElement.addEventListener("pointermove",this._onPointerMove),this.domElement.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(i)&&(this._addPointer(i),i.pointerType==="touch"?this._onTouchStart(i):this._onMouseDown(i)))}function am(i){this.enabled!==!1&&(i.pointerType==="touch"?this._onTouchMove(i):this._onMouseMove(i))}function lm(i){switch(this._removePointer(i),this._pointers.length){case 0:this.domElement.releasePointerCapture(i.pointerId),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(Ll),this.state=dt.NONE;break;case 1:const e=this._pointers[0],t=this._pointerPositions[e];this._onTouchStart({pointerId:e,pageX:t.x,pageY:t.y});break}}function cm(i){let e;switch(i.button){case 0:e=this.mouseButtons.LEFT;break;case 1:e=this.mouseButtons.MIDDLE;break;case 2:e=this.mouseButtons.RIGHT;break;default:e=-1}switch(e){case Ci.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(i),this.state=dt.DOLLY;break;case Ci.ROTATE:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=dt.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=dt.ROTATE}break;case Ci.PAN:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=dt.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=dt.PAN}break;default:this.state=dt.NONE}this.state!==dt.NONE&&this.dispatchEvent(Wo)}function um(i){switch(this.state){case dt.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(i);break;case dt.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(i);break;case dt.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(i);break}}function hm(i){this.enabled===!1||this.enableZoom===!1||this.state!==dt.NONE||(i.preventDefault(),this.dispatchEvent(Wo),this._handleMouseWheel(this._customWheelEvent(i)),this.dispatchEvent(Ll))}function dm(i){this.enabled!==!1&&this._handleKeyDown(i)}function fm(i){switch(this._trackPointer(i),this._pointers.length){case 1:switch(this.touches.ONE){case Ai.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(i),this.state=dt.TOUCH_ROTATE;break;case Ai.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(i),this.state=dt.TOUCH_PAN;break;default:this.state=dt.NONE}break;case 2:switch(this.touches.TWO){case Ai.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(i),this.state=dt.TOUCH_DOLLY_PAN;break;case Ai.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(i),this.state=dt.TOUCH_DOLLY_ROTATE;break;default:this.state=dt.NONE}break;default:this.state=dt.NONE}this.state!==dt.NONE&&this.dispatchEvent(Wo)}function pm(i){switch(this._trackPointer(i),this.state){case dt.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(i),this.update();break;case dt.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(i),this.update();break;case dt.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(i),this.update();break;case dt.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(i),this.update();break;default:this.state=dt.NONE}}function mm(i){this.enabled!==!1&&i.preventDefault()}function gm(i){i.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function _m(i){i.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}/*!
fflate - fast JavaScript compression/decompression
<https://101arrowz.github.io/fflate>
Licensed under MIT. https://github.com/101arrowz/fflate/blob/master/LICENSE
version 0.8.2
*/var Kt=Uint8Array,Ri=Uint16Array,vm=Int32Array,Ul=new Kt([0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0,0,0,0]),Il=new Kt([0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13,0,0]),xm=new Kt([16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15]),Nl=function(i,e){for(var t=new Ri(31),n=0;n<31;++n)t[n]=e+=1<<i[n-1];for(var r=new vm(t[30]),n=1;n<30;++n)for(var s=t[n];s<t[n+1];++s)r[s]=s-t[n]<<5|n;return{b:t,r}},Fl=Nl(Ul,2),Ol=Fl.b,Mm=Fl.r;Ol[28]=258,Mm[258]=28;var Sm=Nl(Il,0),ym=Sm.b,bo=new Ri(32768);for(var mt=0;mt<32768;++mt){var On=(mt&43690)>>1|(mt&21845)<<1;On=(On&52428)>>2|(On&13107)<<2,On=(On&61680)>>4|(On&3855)<<4,bo[mt]=((On&65280)>>8|(On&255)<<8)>>1}var Ji=(function(i,e,t){for(var n=i.length,r=0,s=new Ri(e);r<n;++r)i[r]&&++s[i[r]-1];var o=new Ri(e);for(r=1;r<e;++r)o[r]=o[r-1]+s[r-1]<<1;var a;if(t){a=new Ri(1<<e);var u=15-e;for(r=0;r<n;++r)if(i[r])for(var l=r<<4|i[r],d=e-i[r],h=o[i[r]-1]++<<d,f=h|(1<<d)-1;h<=f;++h)a[bo[h]>>u]=l}else for(a=new Ri(n),r=0;r<n;++r)i[r]&&(a[r]=bo[o[i[r]-1]++]>>15-i[r]);return a}),cr=new Kt(288);for(var mt=0;mt<144;++mt)cr[mt]=8;for(var mt=144;mt<256;++mt)cr[mt]=9;for(var mt=256;mt<280;++mt)cr[mt]=7;for(var mt=280;mt<288;++mt)cr[mt]=8;var Bl=new Kt(32);for(var mt=0;mt<32;++mt)Bl[mt]=5;var Em=Ji(cr,9,1),Tm=Ji(Bl,5,1),Is=function(i){for(var e=i[0],t=1;t<i.length;++t)i[t]>e&&(e=i[t]);return e},un=function(i,e,t){var n=e/8|0;return(i[n]|i[n+1]<<8)>>(e&7)&t},Ns=function(i,e){var t=e/8|0;return(i[t]|i[t+1]<<8|i[t+2]<<16)>>(e&7)},bm=function(i){return(i+7)/8|0},Xo=function(i,e,t){return(e==null||e<0)&&(e=0),(t==null||t>i.length)&&(t=i.length),new Kt(i.subarray(e,t))},Am=["unexpected EOF","invalid block type","invalid length/literal","invalid distance","stream finished","no stream handler",,"no callback","invalid UTF-8 data","extra field too long","date not in range 1980-2099","filename too long","stream finishing","invalid zip data"],rn=function(i,e,t){var n=new Error(e||Am[i]);if(n.code=i,Error.captureStackTrace&&Error.captureStackTrace(n,rn),!t)throw n;return n},wm=function(i,e,t,n){var r=i.length,s=n?n.length:0;if(!r||e.f&&!e.l)return t||new Kt(0);var o=!t,a=o||e.i!=2,u=e.i;o&&(t=new Kt(r*3));var l=function(Y){var ee=t.length;if(Y>ee){var b=new Kt(Math.max(ee*2,Y));b.set(t),t=b}},d=e.f||0,h=e.p||0,f=e.b||0,m=e.l,_=e.d,v=e.m,p=e.n,c=r*8;do{if(!m){d=un(i,h,1);var A=un(i,h+1,3);if(h+=3,A)if(A==1)m=Em,_=Tm,v=9,p=5;else if(A==2){var R=un(i,h,31)+257,P=un(i,h+10,15)+4,I=R+un(i,h+5,31)+1;h+=14;for(var y=new Kt(I),E=new Kt(19),w=0;w<P;++w)E[xm[w]]=un(i,h+w*3,7);h+=P*3;for(var Q=Is(E),j=(1<<Q)-1,Z=Ji(E,Q,1),w=0;w<I;){var re=Z[un(i,h,j)];h+=re&15;var S=re>>4;if(S<16)y[w++]=S;else{var X=0,ae=0;for(S==16?(ae=3+un(i,h,3),h+=2,X=y[w-1]):S==17?(ae=3+un(i,h,7),h+=3):S==18&&(ae=11+un(i,h,127),h+=7);ae--;)y[w++]=X}}var W=y.subarray(0,R),he=y.subarray(R);v=Is(W),p=Is(he),m=Ji(W,v,1),_=Ji(he,p,1)}else rn(1);else{var S=bm(h)+4,M=i[S-4]|i[S-3]<<8,C=S+M;if(C>r){u&&rn(0);break}a&&l(f+M),t.set(i.subarray(S,C),f),e.b=f+=M,e.p=h=C*8,e.f=d;continue}if(h>c){u&&rn(0);break}}a&&l(f+131072);for(var ye=(1<<v)-1,Te=(1<<p)-1,ze=h;;ze=h){var X=m[Ns(i,h)&ye],nt=X>>4;if(h+=X&15,h>c){u&&rn(0);break}if(X||rn(2),nt<256)t[f++]=nt;else if(nt==256){ze=h,m=null;break}else{var it=nt-254;if(nt>264){var w=nt-257,J=Ul[w];it=un(i,h,(1<<J)-1)+Ol[w],h+=J}var L=_[Ns(i,h)&Te],D=L>>4;L||rn(3),h+=L&15;var he=ym[D];if(D>3){var J=Il[D];he+=Ns(i,h)&(1<<J)-1,h+=J}if(h>c){u&&rn(0);break}a&&l(f+131072);var z=f+it;if(f<he){var H=s-he,G=Math.min(he,z);for(H+f<0&&rn(3);f<G;++f)t[f]=n[H+f]}for(;f<z;++f)t[f]=t[f-he]}}e.l=m,e.p=ze,e.b=f,e.f=d,m&&(d=1,e.m=v,e.d=_,e.n=p)}while(!d);return f!=t.length&&o?Xo(t,0,f):t.subarray(0,f)},Rm=new Kt(0),mn=function(i,e){return i[e]|i[e+1]<<8},hn=function(i,e){return(i[e]|i[e+1]<<8|i[e+2]<<16|i[e+3]<<24)>>>0},Fs=function(i,e){return hn(i,e)+hn(i,e+4)*4294967296};function Cm(i,e){return wm(i,{i:2},e&&e.out,e&&e.dictionary)}var Ao=typeof TextDecoder<"u"&&new TextDecoder,Pm=0;try{Ao.decode(Rm,{stream:!0}),Pm=1}catch{}var Dm=function(i){for(var e="",t=0;;){var n=i[t++],r=(n>127)+(n>223)+(n>239);if(t+r>i.length)return{s:e,r:Xo(i,t-1)};r?r==3?(n=((n&15)<<18|(i[t++]&63)<<12|(i[t++]&63)<<6|i[t++]&63)-65536,e+=String.fromCharCode(55296|n>>10,56320|n&1023)):r&1?e+=String.fromCharCode((n&31)<<6|i[t++]&63):e+=String.fromCharCode((n&15)<<12|(i[t++]&63)<<6|i[t++]&63):e+=String.fromCharCode(n)}};function Lm(i,e){if(e){for(var t="",n=0;n<i.length;n+=16384)t+=String.fromCharCode.apply(null,i.subarray(n,n+16384));return t}else{if(Ao)return Ao.decode(i);var r=Dm(i),s=r.s,t=r.r;return t.length&&rn(8),s}}var Um=function(i,e){return e+30+mn(i,e+26)+mn(i,e+28)},Im=function(i,e,t){var n=mn(i,e+28),r=Lm(i.subarray(e+46,e+46+n),!(mn(i,e+8)&2048)),s=e+46+n,o=hn(i,e+20),a=t&&o==4294967295?Nm(i,s):[o,hn(i,e+24),hn(i,e+42)],u=a[0],l=a[1],d=a[2];return[mn(i,e+10),u,l,r,s+mn(i,e+30)+mn(i,e+32),d]},Nm=function(i,e){for(;mn(i,e)!=1;e+=4+mn(i,e+2));return[Fs(i,e+12),Fs(i,e+4),Fs(i,e+20)]};function Fm(i,e){for(var t={},n=i.length-22;hn(i,n)!=101010256;--n)(!n||i.length-n>65558)&&rn(13);var r=mn(i,n+8);if(!r)return{};var s=hn(i,n+16),o=s==4294967295||r==65535;if(o){var a=hn(i,n-12);o=hn(i,a)==101075792,o&&(r=hn(i,a+32),s=hn(i,a+48))}for(var u=0;u<r;++u){var l=Im(i,s,o),d=l[0],h=l[1],f=l[2],m=l[3],_=l[4],v=l[5],p=Um(i,v);s=_,d?d==8?t[m]=Cm(i.subarray(p,p+h),{out:new Kt(f)}):rn(14,"unknown compression type "+d):t[m]=Xo(i,p,p+h)}return t}const Os=Dt;class Om extends Wn{constructor(e){super(e),this.availableExtensions=[]}load(e,t,n,r){const s=this,o=new Vo(s.manager);o.setPath(s.path),o.setResponseType("arraybuffer"),o.setRequestHeader(s.requestHeader),o.setWithCredentials(s.withCredentials),o.load(e,function(a){try{t(s.parse(a))}catch(u){r?r(u):console.error(u),s.manager.itemError(e)}},n,r)}parse(e){const t=this,n=new hu(this.manager);function r(L){let D=null,z=null,H,G;const Y=[],ee=[];let b;const ne={},q={},me={},K=new TextDecoder;try{D=Fm(new Uint8Array(L))}catch(Pe){if(Pe instanceof ReferenceError)return console.error("THREE.3MFLoader: fflate missing and file is compressed."),null}let Ke=null;for(z in D)z.match(/\_rels\/.rels$/)?H=z:z.match(/3D\/_rels\/.*\.model\.rels$/)?G=z:z.match(/^3D\/[^\/]*\.model$/)?Ke=z:z.match(/^3D\/.*\/.*\.model$/)?Y.push(z):z.match(/^3D\/Textures?\/.*/)&&ee.push(z);if(Y.push(Ke),H===void 0)throw new Error("THREE.ThreeMFLoader: Cannot find relationship file `rels` in 3MF archive.");const ue=D[H],Ce=K.decode(ue),$e=s(Ce);if(G){const Pe=D[G],T=K.decode(Pe);b=s(T)}for(let Pe=0;Pe<Y.length;Pe++){const T=Y[Pe],g=D[T],O=K.decode(g),te=new DOMParser().parseFromString(O,"application/xml");te.documentElement.nodeName.toLowerCase()!=="model"&&console.error("THREE.3MFLoader: Error loading 3MF - no 3MF document found: ",T);const se=te.querySelector("model"),$={};for(let pe=0;pe<se.attributes.length;pe++){const we=se.attributes[pe];we.name.match(/^xmlns:(.+)$/)&&($[we.value]=RegExp.$1)}const ve=R(se);ve.xml=se,0<Object.keys($).length&&(ve.extensions=$),ne[T]=ve}for(let Pe=0;Pe<ee.length;Pe++){const T=ee[Pe];me[T]=D[T].buffer}return{rels:$e,modelRels:b,model:ne,printTicket:q,texture:me}}function s(L){const D=[],H=new DOMParser().parseFromString(L,"application/xml").querySelectorAll("Relationship");for(let G=0;G<H.length;G++){const Y=H[G],ee={target:Y.getAttribute("Target"),id:Y.getAttribute("Id"),type:Y.getAttribute("Type")};D.push(ee)}return D}function o(L){const D={};for(let z=0;z<L.length;z++){const H=L[z],G=H.getAttribute("name");0<=["Title","Designer","Description","Copyright","LicenseTerms","Rating","CreationDate","ModificationDate"].indexOf(G)&&(D[G]=H.textContent)}return D}function a(L){const D={id:L.getAttribute("id"),basematerials:[]},z=L.querySelectorAll("base");for(let H=0;H<z.length;H++){const G=z[H],Y=_(G);Y.index=H,D.basematerials.push(Y)}return D}function u(L){return{id:L.getAttribute("id"),path:L.getAttribute("path"),contenttype:L.getAttribute("contenttype"),tilestyleu:L.getAttribute("tilestyleu"),tilestylev:L.getAttribute("tilestylev"),filter:L.getAttribute("filter")}}function l(L){const D={id:L.getAttribute("id"),texid:L.getAttribute("texid"),displaypropertiesid:L.getAttribute("displaypropertiesid")},z=L.querySelectorAll("tex2coord"),H=[];for(let G=0;G<z.length;G++){const Y=z[G],ee=Y.getAttribute("u"),b=Y.getAttribute("v");H.push(parseFloat(ee),parseFloat(b))}return D.uvs=new Float32Array(H),D}function d(L){const D={id:L.getAttribute("id"),displaypropertiesid:L.getAttribute("displaypropertiesid")},z=L.querySelectorAll("color"),H=[],G=new je;for(let Y=0;Y<z.length;Y++){const b=z[Y].getAttribute("color");G.setStyle(b.substring(0,7),Os),H.push(G.r,G.g,G.b)}return D.colors=new Float32Array(H),D}function h(L){const D=L.children,z={};for(let H=0;H<D.length;H++){const G={type:D[H].nodeName.substring(2)};for(let Y=0;Y<D[H].attributes.length;Y++){const ee=D[H].attributes[Y];ee.specified&&(G[ee.name]=ee.value)}z[D[H].getAttribute("identifier")]=G}return z}function f(L){const D={id:L.getAttribute("id"),displayname:L.getAttribute("displayname")},z=L.children,H={};for(let G=0;G<z.length;G++){const Y=z[G];if(Y.nodeName==="i:in"||Y.nodeName==="i:out")H[Y.nodeName==="i:in"?"inputs":"outputs"]=h(Y);else{const ee=Y.children,b={op:Y.nodeName.substring(2),identifier:Y.getAttribute("identifier")};for(let ne=0;ne<ee.length;ne++)b[ee[ne].nodeName.substring(2)]=h(ee[ne]);H[b.identifier]=b}}return D.operations=H,D}function m(L){const D={id:L.getAttribute("id")},z=L.querySelectorAll("pbmetallic"),H=[];for(let G=0;G<z.length;G++){const Y=z[G];H.push({name:Y.getAttribute("name"),metallicness:parseFloat(Y.getAttribute("metallicness")),roughness:parseFloat(Y.getAttribute("roughness"))})}return D.data=H,D}function _(L){const D={};return D.name=L.getAttribute("name"),D.displaycolor=L.getAttribute("displaycolor"),D.displaypropertiesid=L.getAttribute("displaypropertiesid"),D}function v(L){const D={},z=[],H=L.querySelectorAll("vertices vertex");for(let b=0;b<H.length;b++){const ne=H[b],q=ne.getAttribute("x"),me=ne.getAttribute("y"),K=ne.getAttribute("z");z.push(parseFloat(q),parseFloat(me),parseFloat(K))}D.vertices=new Float32Array(z);const G=[],Y=[],ee=L.querySelectorAll("triangles triangle");for(let b=0;b<ee.length;b++){const ne=ee[b],q=ne.getAttribute("v1"),me=ne.getAttribute("v2"),K=ne.getAttribute("v3"),Ke=ne.getAttribute("p1"),ue=ne.getAttribute("p2"),Ce=ne.getAttribute("p3"),$e=ne.getAttribute("pid"),Pe={};Pe.v1=parseInt(q,10),Pe.v2=parseInt(me,10),Pe.v3=parseInt(K,10),Y.push(Pe.v1,Pe.v2,Pe.v3),Ke&&(Pe.p1=parseInt(Ke,10)),ue&&(Pe.p2=parseInt(ue,10)),Ce&&(Pe.p3=parseInt(Ce,10)),$e&&(Pe.pid=$e),0<Object.keys(Pe).length&&G.push(Pe)}return D.triangleProperties=G,D.triangles=new Uint32Array(Y),D}function p(L){const D=[],z=L.querySelectorAll("component");for(let H=0;H<z.length;H++){const G=z[H],Y=c(G);D.push(Y)}return D}function c(L){const D={};D.objectId=L.getAttribute("objectid");const z=L.getAttribute("transform");return z&&(D.transform=A(z)),D}function A(L){const D=[];L.split(" ").forEach(function(H){D.push(parseFloat(H))});const z=new gt;return z.set(D[0],D[3],D[6],D[9],D[1],D[4],D[7],D[10],D[2],D[5],D[8],D[11],0,0,0,1),z}function S(L){const D={type:L.getAttribute("type")},z=L.getAttribute("id");z&&(D.id=z);const H=L.getAttribute("pid");H&&(D.pid=H);const G=L.getAttribute("pindex");G&&(D.pindex=G);const Y=L.getAttribute("thumbnail");Y&&(D.thumbnail=Y);const ee=L.getAttribute("partnumber");ee&&(D.partnumber=ee);const b=L.getAttribute("name");b&&(D.name=b);const ne=L.querySelector("mesh");ne&&(D.mesh=v(ne));const q=L.querySelector("components");return q&&(D.components=p(q)),D}function M(L){const D={};D.basematerials={};const z=L.querySelectorAll("basematerials");for(let q=0;q<z.length;q++){const me=z[q],K=a(me);D.basematerials[K.id]=K}D.texture2d={};const H=L.querySelectorAll("texture2d");for(let q=0;q<H.length;q++){const me=H[q],K=u(me);D.texture2d[K.id]=K}D.colorgroup={};const G=L.querySelectorAll("colorgroup");for(let q=0;q<G.length;q++){const me=G[q],K=d(me);D.colorgroup[K.id]=K}const Y=L.querySelectorAll("implicitfunction");Y.length>0&&(D.implicitfunction={});for(let q=0;q<Y.length;q++){const me=Y[q],K=f(me);D.implicitfunction[K.id]=K}D.pbmetallicdisplayproperties={};const ee=L.querySelectorAll("pbmetallicdisplayproperties");for(let q=0;q<ee.length;q++){const me=ee[q],K=m(me);D.pbmetallicdisplayproperties[K.id]=K}D.texture2dgroup={};const b=L.querySelectorAll("texture2dgroup");for(let q=0;q<b.length;q++){const me=b[q],K=l(me);D.texture2dgroup[K.id]=K}D.object={};const ne=L.querySelectorAll("object");for(let q=0;q<ne.length;q++){const me=ne[q],K=S(me);D.object[K.id]=K}return D}function C(L){const D=[],z=L.querySelectorAll("item");for(let H=0;H<z.length;H++){const G=z[H],Y={objectId:G.getAttribute("objectid")},ee=G.getAttribute("transform");ee&&(Y.transform=A(ee)),D.push(Y)}return D}function R(L){const D={unit:L.getAttribute("unit")||"millimeter"},z=L.querySelectorAll("metadata");z&&(D.metadata=o(z));const H=L.querySelector("resources");H&&(D.resources=M(H));const G=L.querySelector("build");return G&&(D.build=C(G)),D}function P(L,D,z,H){const G=L.texid,ee=z.resources.texture2d[G];if(ee){const b=H[ee.path],ne=ee.contenttype,q=new Blob([b],{type:ne}),me=URL.createObjectURL(q),K=n.load(me,function(){URL.revokeObjectURL(me)});switch(K.colorSpace=Os,ee.tilestyleu){case"wrap":K.wrapS=ti;break;case"mirror":K.wrapS=Qi;break;case"none":case"clamp":K.wrapS=wn;break;default:K.wrapS=ti}switch(ee.tilestylev){case"wrap":K.wrapT=ti;break;case"mirror":K.wrapT=Qi;break;case"none":case"clamp":K.wrapT=wn;break;default:K.wrapT=ti}switch(ee.filter){case"auto":K.magFilter=Gt,K.minFilter=Rn;break;case"linear":K.magFilter=Gt,K.minFilter=Gt,K.generateMipmaps=!1;break;case"nearest":K.magFilter=Zt,K.minFilter=Zt,K.generateMipmaps=!1;break;default:K.magFilter=Gt,K.minFilter=Rn}return K}else return null}function I(L,D,z,H,G,Y,ee){const b=ee.pindex,ne={};for(let K=0,Ke=D.length;K<Ke;K++){const ue=D[K],Ce=ue.p1!==void 0?ue.p1:b;ne[Ce]===void 0&&(ne[Ce]=[]),ne[Ce].push(ue)}const q=Object.keys(ne),me=[];for(let K=0,Ke=q.length;K<Ke;K++){const ue=q[K],Ce=ne[ue],$e=L.basematerials[ue],Pe=ae($e,H,G,Y,ee,W),T=new yt,g=[],O=z.vertices;for(let se=0,$=Ce.length;se<$;se++){const ve=Ce[se];g.push(O[ve.v1*3+0]),g.push(O[ve.v1*3+1]),g.push(O[ve.v1*3+2]),g.push(O[ve.v2*3+0]),g.push(O[ve.v2*3+1]),g.push(O[ve.v2*3+2]),g.push(O[ve.v3*3+0]),g.push(O[ve.v3*3+1]),g.push(O[ve.v3*3+2])}T.setAttribute("position",new lt(g,3));const te=new Ft(T,Pe);me.push(te)}return me}function y(L,D,z,H,G,Y,ee){const b=new yt,ne=[],q=[],me=z.vertices,K=L.uvs;for(let $e=0,Pe=D.length;$e<Pe;$e++){const T=D[$e];ne.push(me[T.v1*3+0]),ne.push(me[T.v1*3+1]),ne.push(me[T.v1*3+2]),ne.push(me[T.v2*3+0]),ne.push(me[T.v2*3+1]),ne.push(me[T.v2*3+2]),ne.push(me[T.v3*3+0]),ne.push(me[T.v3*3+1]),ne.push(me[T.v3*3+2]),q.push(K[T.p1*2+0]),q.push(K[T.p1*2+1]),q.push(K[T.p2*2+0]),q.push(K[T.p2*2+1]),q.push(K[T.p3*2+0]),q.push(K[T.p3*2+1])}b.setAttribute("position",new lt(ne,3)),b.setAttribute("uv",new lt(q,2));const Ke=ae(L,H,G,Y,ee,P),ue=new Ur({map:Ke,flatShading:!0});return new Ft(b,ue)}function E(L,D,z,H){const G=new yt,Y=[],ee=[],b=z.vertices,ne=L.colors;for(let K=0,Ke=D.length;K<Ke;K++){const ue=D[K],Ce=ue.v1,$e=ue.v2,Pe=ue.v3;Y.push(b[Ce*3+0]),Y.push(b[Ce*3+1]),Y.push(b[Ce*3+2]),Y.push(b[$e*3+0]),Y.push(b[$e*3+1]),Y.push(b[$e*3+2]),Y.push(b[Pe*3+0]),Y.push(b[Pe*3+1]),Y.push(b[Pe*3+2]);const T=ue.p1!==void 0?ue.p1:H.pindex,g=ue.p2!==void 0?ue.p2:T,O=ue.p3!==void 0?ue.p3:T;ee.push(ne[T*3+0]),ee.push(ne[T*3+1]),ee.push(ne[T*3+2]),ee.push(ne[g*3+0]),ee.push(ne[g*3+1]),ee.push(ne[g*3+2]),ee.push(ne[O*3+0]),ee.push(ne[O*3+1]),ee.push(ne[O*3+2])}G.setAttribute("position",new lt(Y,3)),G.setAttribute("color",new lt(ee,3));const q=new Ur({vertexColors:!0,flatShading:!0});return new Ft(G,q)}function w(L){const D=new yt;D.setIndex(new Bt(L.triangles,1)),D.setAttribute("position",new Bt(L.vertices,3));const z=new Ur({name:Wn.DEFAULT_MATERIAL_NAME,color:16777215,flatShading:!0});return new Ft(D,z)}function Q(L,D,z,H,G,Y){const ee=Object.keys(L),b=[];for(let ne=0,q=ee.length;ne<q;ne++){const me=ee[ne],K=L[me];switch(j(me,H)){case"material":const ue=H.resources.basematerials[me],Ce=I(ue,K,D,z,H,G,Y);for(let T=0,g=Ce.length;T<g;T++)b.push(Ce[T]);break;case"texture":const $e=H.resources.texture2dgroup[me];b.push(y($e,K,D,z,H,G,Y));break;case"vertexColors":const Pe=H.resources.colorgroup[me];b.push(E(Pe,K,D,Y));break;case"default":b.push(w(D));break;default:console.error("THREE.3MFLoader: Unsupported resource type.")}}if(Y.name)for(let ne=0;ne<b.length;ne++)b[ne].name=Y.name;return b}function j(L,D){return D.resources.texture2dgroup[L]!==void 0?"texture":D.resources.basematerials[L]!==void 0?"material":D.resources.colorgroup[L]!==void 0?"vertexColors":L==="default"?"default":void 0}function Z(L,D){const z={},H=L.triangleProperties,G=D.pid;for(let Y=0,ee=H.length;Y<ee;Y++){const b=H[Y];let ne=b.pid!==void 0?b.pid:G;ne===void 0&&(ne="default"),z[ne]===void 0&&(z[ne]=[]),z[ne].push(b)}return z}function re(L,D,z,H,G){const Y=new zn,ee=Z(L,G),b=Q(ee,L,D,z,H,G);for(let ne=0,q=b.length;ne<q;ne++)Y.add(b[ne]);return Y}function X(L,D,z){if(!L)return;const H=[],G=Object.keys(L);for(let Y=0;Y<G.length;Y++){const ee=G[Y];for(let b=0;b<t.availableExtensions.length;b++){const ne=t.availableExtensions[b];ne.ns===ee&&H.push(ne)}}for(let Y=0;Y<H.length;Y++){const ee=H[Y];ee.apply(z,L[ee.ns],D)}}function ae(L,D,z,H,G,Y){return L.build!==void 0||(L.build=Y(L,D,z,H,G)),L.build}function W(L,D,z){let H;const G=L.displaypropertiesid,Y=z.resources.pbmetallicdisplayproperties;if(G!==null&&Y[G]!==void 0){const q=Y[G].data[L.index];H=new El({flatShading:!0,roughness:q.roughness,metalness:q.metallicness})}else H=new Ur({flatShading:!0});H.name=L.name;const ee=L.displaycolor,b=ee.substring(0,7);return H.color.setStyle(b,Os),ee.length===9&&(H.opacity=parseInt(ee.charAt(7)+ee.charAt(8),16)/255),H}function he(L,D,z,H){const G=new zn;for(let Y=0;Y<L.length;Y++){const ee=L[Y];let b=D[ee.objectId];b===void 0&&(ye(ee.objectId,D,z,H),b=D[ee.objectId]);const ne=b.clone(),q=ee.transform;q&&ne.applyMatrix4(q),G.add(ne)}return G}function ye(L,D,z,H){const G=z.resources.object[L];if(G.mesh){const Y=G.mesh,ee=z.extensions,b=z.xml;X(ee,Y,b),D[G.id]=ae(Y,D,z,H,G,re)}else{const Y=G.components;D[G.id]=ae(Y,D,z,H,G,he)}G.name&&(D[G.id].name=G.name),z.resources.implicitfunction&&console.warn("THREE.ThreeMFLoader: Implicit Functions are implemented in data-only.",z.resources.implicitfunction)}function Te(L){const D=L.model,z=L.modelRels,H={},G=Object.keys(D),Y={};if(z)for(let ee=0,b=z.length;ee<b;ee++){const ne=z[ee],q=ne.target.substring(1);L.texture[q]&&(Y[ne.target]=L.texture[q])}for(let ee=0;ee<G.length;ee++){const b=G[ee],ne=D[b],q=Object.keys(ne.resources.object);for(let me=0;me<q.length;me++){const K=q[me];ye(K,H,ne,Y)}}return H}function ze(L){for(let D=0;D<L.length;D++){const z=L[D];if(z.target.split(".").pop().toLowerCase()==="model")return z}}function nt(L,D){const z=new zn,H=ze(D.rels),G=D.model[H.target.substring(1)].build;for(let Y=0;Y<G.length;Y++){const ee=G[Y],b=L[ee.objectId].clone(),ne=ee.transform;ne&&b.applyMatrix4(ne),z.add(b)}return z}const it=r(e),J=Te(it);return nt(J,it)}addExtension(e){this.availableExtensions.push(e)}}const Vt=new je;class Bm extends Wn{constructor(e){super(e),this.propertyNameMapping={},this.customPropertyMapping={}}load(e,t,n,r){const s=this,o=new Vo(this.manager);o.setPath(this.path),o.setResponseType("arraybuffer"),o.setRequestHeader(this.requestHeader),o.setWithCredentials(this.withCredentials),o.load(e,function(a){try{t(s.parse(a))}catch(u){r?r(u):console.error(u),s.manager.itemError(e)}},n,r)}setPropertyNameMapping(e){this.propertyNameMapping=e}setCustomPropertyNameMapping(e){this.customPropertyMapping=e}parse(e){function t(p,c=0){const A=/^ply([\s\S]*)end_header(\r\n|\r|\n)/;let S="";const M=A.exec(p);M!==null&&(S=M[1]);const C={comments:[],elements:[],headerLength:c,objInfo:""},R=S.split(/\r\n|\r|\n/);let P;function I(y,E){const w={type:y[0]};return w.type==="list"?(w.name=y[3],w.countType=y[1],w.itemType=y[2]):w.name=y[1],w.name in E&&(w.name=E[w.name]),w}for(let y=0;y<R.length;y++){let E=R[y];if(E=E.trim(),E==="")continue;const w=E.split(/\s+/),Q=w.shift();switch(E=w.join(" "),Q){case"format":C.format=w[0],C.version=w[1];break;case"comment":C.comments.push(E);break;case"element":P!==void 0&&C.elements.push(P),P={},P.name=w[0],P.count=parseInt(w[1]),P.properties=[];break;case"property":P.properties.push(I(w,v.propertyNameMapping));break;case"obj_info":C.objInfo=E;break;default:console.log("unhandled",Q,w)}}return P!==void 0&&C.elements.push(P),C}function n(p,c){switch(c){case"char":case"uchar":case"short":case"ushort":case"int":case"uint":case"int8":case"uint8":case"int16":case"uint16":case"int32":case"uint32":return parseInt(p);case"float":case"double":case"float32":case"float64":return parseFloat(p)}}function r(p,c){const A={};for(let S=0;S<p.length;S++){if(c.empty())return null;if(p[S].type==="list"){const M=[],C=n(c.next(),p[S].countType);for(let R=0;R<C;R++){if(c.empty())return null;M.push(n(c.next(),p[S].itemType))}A[p[S].name]=M}else A[p[S].name]=n(c.next(),p[S].type)}return A}function s(){const p={indices:[],vertices:[],normals:[],uvs:[],faceVertexUvs:[],colors:[],faceVertexColors:[]};for(const c of Object.keys(v.customPropertyMapping))p[c]=[];return p}function o(p){const c=p.map(S=>S.name);function A(S){for(let M=0,C=S.length;M<C;M++){const R=S[M];if(c.includes(R))return R}return null}return{attrX:A(["x","px","posx"])||"x",attrY:A(["y","py","posy"])||"y",attrZ:A(["z","pz","posz"])||"z",attrNX:A(["nx","normalx"]),attrNY:A(["ny","normaly"]),attrNZ:A(["nz","normalz"]),attrS:A(["s","u","texture_u","tx"]),attrT:A(["t","v","texture_v","ty"]),attrR:A(["red","diffuse_red","r","diffuse_r"]),attrG:A(["green","diffuse_green","g","diffuse_g"]),attrB:A(["blue","diffuse_blue","b","diffuse_b"])}}function a(p,c){const A=s(),S=/end_header\s+(\S[\s\S]*\S|\S)\s*$/;let M,C;(C=S.exec(p))!==null?M=C[1].split(/\s+/):M=[];const R=new zm(M);e:for(let P=0;P<c.elements.length;P++){const I=c.elements[P],y=o(I.properties);for(let E=0;E<I.count;E++){const w=r(I.properties,R);if(!w)break e;l(A,I.name,w,y)}}return u(A)}function u(p){let c=new yt;p.indices.length>0&&c.setIndex(p.indices),c.setAttribute("position",new lt(p.vertices,3)),p.normals.length>0&&c.setAttribute("normal",new lt(p.normals,3)),p.uvs.length>0&&c.setAttribute("uv",new lt(p.uvs,2)),p.colors.length>0&&c.setAttribute("color",new lt(p.colors,3)),(p.faceVertexUvs.length>0||p.faceVertexColors.length>0)&&(c=c.toNonIndexed(),p.faceVertexUvs.length>0&&c.setAttribute("uv",new lt(p.faceVertexUvs,2)),p.faceVertexColors.length>0&&c.setAttribute("color",new lt(p.faceVertexColors,3)));for(const A of Object.keys(v.customPropertyMapping))p[A].length>0&&c.setAttribute(A,new lt(p[A],v.customPropertyMapping[A].length));return c.computeBoundingSphere(),c}function l(p,c,A,S){if(c==="vertex"){p.vertices.push(A[S.attrX],A[S.attrY],A[S.attrZ]),S.attrNX!==null&&S.attrNY!==null&&S.attrNZ!==null&&p.normals.push(A[S.attrNX],A[S.attrNY],A[S.attrNZ]),S.attrS!==null&&S.attrT!==null&&p.uvs.push(A[S.attrS],A[S.attrT]),S.attrR!==null&&S.attrG!==null&&S.attrB!==null&&(Vt.setRGB(A[S.attrR]/255,A[S.attrG]/255,A[S.attrB]/255,Dt),p.colors.push(Vt.r,Vt.g,Vt.b));for(const M of Object.keys(v.customPropertyMapping))for(const C of v.customPropertyMapping[M])p[M].push(A[C])}else if(c==="face"){const M=A.vertex_indices||A.vertex_index,C=A.texcoord;M.length===3?(p.indices.push(M[0],M[1],M[2]),C&&C.length===6&&(p.faceVertexUvs.push(C[0],C[1]),p.faceVertexUvs.push(C[2],C[3]),p.faceVertexUvs.push(C[4],C[5]))):M.length===4&&(p.indices.push(M[0],M[1],M[3]),p.indices.push(M[1],M[2],M[3])),S.attrR!==null&&S.attrG!==null&&S.attrB!==null&&(Vt.setRGB(A[S.attrR]/255,A[S.attrG]/255,A[S.attrB]/255,Dt),p.faceVertexColors.push(Vt.r,Vt.g,Vt.b),p.faceVertexColors.push(Vt.r,Vt.g,Vt.b),p.faceVertexColors.push(Vt.r,Vt.g,Vt.b))}}function d(p,c){const A={};let S=0;for(let M=0;M<c.length;M++){const C=c[M],R=C.valueReader;if(C.type==="list"){const P=[],I=C.countReader.read(p+S);S+=C.countReader.size;for(let y=0;y<I;y++)P.push(R.read(p+S)),S+=R.size;A[C.name]=P}else A[C.name]=R.read(p+S),S+=R.size}return[A,S]}function h(p,c,A){function S(M,C,R){switch(C){case"int8":case"char":return{read:P=>M.getInt8(P),size:1};case"uint8":case"uchar":return{read:P=>M.getUint8(P),size:1};case"int16":case"short":return{read:P=>M.getInt16(P,R),size:2};case"uint16":case"ushort":return{read:P=>M.getUint16(P,R),size:2};case"int32":case"int":return{read:P=>M.getInt32(P,R),size:4};case"uint32":case"uint":return{read:P=>M.getUint32(P,R),size:4};case"float32":case"float":return{read:P=>M.getFloat32(P,R),size:4};case"float64":case"double":return{read:P=>M.getFloat64(P,R),size:8}}}for(let M=0,C=p.length;M<C;M++){const R=p[M];R.type==="list"?(R.countReader=S(c,R.countType,A),R.valueReader=S(c,R.itemType,A)):R.valueReader=S(c,R.type,A)}}function f(p,c){const A=s(),S=c.format==="binary_little_endian",M=new DataView(p,c.headerLength);let C,R=0;for(let P=0;P<c.elements.length;P++){const I=c.elements[P],y=I.properties,E=o(y);h(y,M,S);for(let w=0;w<I.count;w++){C=d(R,y),R+=C[1];const Q=C[0];l(A,I.name,Q,E)}}return u(A)}function m(p){let c=0,A=!0,S="";const M=[],C=new TextDecoder().decode(p.subarray(0,5)),R=/^ply\r\n/.test(C);do{const P=String.fromCharCode(p[c++]);P!==`
`&&P!=="\r"?S+=P:(S==="end_header"&&(A=!1),S!==""&&(M.push(S),S=""))}while(A&&c<p.length);return R===!0&&c++,{headerText:M.join("\r")+"\r",headerLength:c}}let _;const v=this;if(e instanceof ArrayBuffer){const p=new Uint8Array(e),{headerText:c,headerLength:A}=m(p),S=t(c,A);if(S.format==="ascii"){const M=new TextDecoder().decode(p);_=a(M,S)}else _=f(e,S)}else _=a(e,t(e));return _}}class zm{constructor(e){this.arr=e,this.i=0}empty(){return this.i>=this.arr.length}next(){return this.arr[this.i++]}}class Hm extends Wn{constructor(e){super(e)}load(e,t,n,r){const s=this,o=new Vo(this.manager);o.setPath(this.path),o.setResponseType("arraybuffer"),o.setRequestHeader(this.requestHeader),o.setWithCredentials(this.withCredentials),o.load(e,function(a){try{t(s.parse(a))}catch(u){r?r(u):console.error(u),s.manager.itemError(e)}},n,r)}parse(e){function t(l){const d=new DataView(l),h=32/8*3+32/8*3*3+16/8,f=d.getUint32(80,!0);if(80+32/8+f*h===d.byteLength)return!0;const _=[115,111,108,105,100];for(let v=0;v<5;v++)if(n(_,d,v))return!1;return!0}function n(l,d,h){for(let f=0,m=l.length;f<m;f++)if(l[f]!==d.getUint8(h+f))return!1;return!0}function r(l){const d=new DataView(l),h=d.getUint32(80,!0);let f,m,_,v=!1,p,c,A,S,M;for(let w=0;w<70;w++)d.getUint32(w,!1)==1129270351&&d.getUint8(w+4)==82&&d.getUint8(w+5)==61&&(v=!0,p=new Float32Array(h*3*3),c=d.getUint8(w+6)/255,A=d.getUint8(w+7)/255,S=d.getUint8(w+8)/255,M=d.getUint8(w+9)/255);const C=84,R=50,P=new yt,I=new Float32Array(h*3*3),y=new Float32Array(h*3*3),E=new je;for(let w=0;w<h;w++){const Q=C+w*R,j=d.getFloat32(Q,!0),Z=d.getFloat32(Q+4,!0),re=d.getFloat32(Q+8,!0);if(v){const X=d.getUint16(Q+48,!0);(X&32768)===0?(f=(X&31)/31,m=(X>>5&31)/31,_=(X>>10&31)/31):(f=c,m=A,_=S)}for(let X=1;X<=3;X++){const ae=Q+X*12,W=w*3*3+(X-1)*3;I[W]=d.getFloat32(ae,!0),I[W+1]=d.getFloat32(ae+4,!0),I[W+2]=d.getFloat32(ae+8,!0),y[W]=j,y[W+1]=Z,y[W+2]=re,v&&(E.setRGB(f,m,_,Dt),p[W]=E.r,p[W+1]=E.g,p[W+2]=E.b)}}return P.setAttribute("position",new Bt(I,3)),P.setAttribute("normal",new Bt(y,3)),v&&(P.setAttribute("color",new Bt(p,3)),P.hasColors=!0,P.alpha=M),P}function s(l){const d=new yt,h=/solid([\s\S]*?)endsolid/g,f=/facet([\s\S]*?)endfacet/g,m=/solid\s(.+)/;let _=0;const v=/[\s]+([+-]?(?:\d*)(?:\.\d*)?(?:[eE][+-]?\d+)?)/.source,p=new RegExp("vertex"+v+v+v,"g"),c=new RegExp("normal"+v+v+v,"g"),A=[],S=[],M=[],C=new B;let R,P=0,I=0,y=0;for(;(R=h.exec(l))!==null;){I=y;const E=R[0],w=(R=m.exec(E))!==null?R[1]:"";for(M.push(w);(R=f.exec(E))!==null;){let Z=0,re=0;const X=R[0];for(;(R=c.exec(X))!==null;)C.x=parseFloat(R[1]),C.y=parseFloat(R[2]),C.z=parseFloat(R[3]),re++;for(;(R=p.exec(X))!==null;)A.push(parseFloat(R[1]),parseFloat(R[2]),parseFloat(R[3])),S.push(C.x,C.y,C.z),Z++,y++;re!==1&&console.error("THREE.STLLoader: Something isn't right with the normal of face number "+_),Z!==3&&console.error("THREE.STLLoader: Something isn't right with the vertices of face number "+_),_++}const Q=I,j=y-I;d.userData.groupNames=M,d.addGroup(Q,j,P),P++}return d.setAttribute("position",new lt(A,3)),d.setAttribute("normal",new lt(S,3)),d}function o(l){return typeof l!="string"?new TextDecoder().decode(l):l}function a(l){if(typeof l=="string"){const d=new Uint8Array(l.length);for(let h=0;h<l.length;h++)d[h]=l.charCodeAt(h)&255;return d.buffer||d}else return l}const u=a(e);return t(u)?r(u):s(o(e))}}const Qa=5*1024*1024,el=i=>{if(!i)return null;const e=Number(i);return Number.isFinite(e)&&e>0?e:null},tl=i=>i===null?null:i<1024?`${i} B`:i<1024*1024?`${(i/1024).toFixed(1)} KB`:`${(i/(1024*1024)).toFixed(1)} MB`,Vm=({url:i,height:e=480,format:t="ply"})=>{const n=Ie.useRef(null),r=Ie.useRef(null),s=Ie.useRef(null),o=Ie.useRef(null),a=Ie.useRef(null),u=Ie.useRef(null),l=Ie.useRef(null),d=Ie.useRef([]),h=Ie.useRef(null),f=Ie.useRef(null),m=Ie.useRef(null),_=Ie.useRef(null),v=Ie.useRef(null),p=Ie.useRef(null),c=Ie.useRef([]),A=Ie.useRef(null),S=Ie.useRef(new Map),M=Ie.useRef(e),[C,R]=Ie.useState(null),[P,I]=Ie.useState(!0),[y,E]=Ie.useState(!1),[w,Q]=Ie.useState(!1),[j,Z]=Ie.useState(!1),[re,X]=Ie.useState(!1),[ae,W]=Ie.useState(!1),[he,ye]=Ie.useState(!1),[Te,ze]=Ie.useState("Z"),[nt,it]=Ie.useState(0),[J,L]=Ie.useState(null),[D,z]=Ie.useState(!1),[H,G]=Ie.useState(!1),[Y,ee]=Ie.useState(null),[b,ne]=Ie.useState(null),[q,me]=Ie.useState("checking"),[K,Ke]=Ie.useState(!1),[ue,Ce]=Ie.useState(0),[$e,Pe]=Ie.useState(null),[T,g]=Ie.useState(null),O=Ie.useRef(P),te=Ie.useRef(y),se=Ie.useRef(w),$=Ie.useRef(j),ve=`${t}:${i}`;Ie.useEffect(()=>{O.current=P},[P]),Ie.useEffect(()=>{te.current=y},[y]),Ie.useEffect(()=>{se.current=w},[w]),Ie.useEffect(()=>{$.current=j},[j]),Ie.useEffect(()=>{M.current=e;const le=requestAnimationFrame(()=>A.current?.());return()=>cancelAnimationFrame(le)},[e]);const pe=le=>{d.current.forEach(Ee=>{Ee.visible=le})},we=le=>{const Ee=l.current;Ee&&Ee.traverse(Be=>{Be.isMesh&&Be.material&&(Array.isArray(Be.material)?Be.material:[Be.material]).forEach(ct=>{ct&&"wireframe"in ct&&(ct.wireframe=le,ct.needsUpdate=!0)})})},Ue=(le,Ee,Be,Ge)=>{const ct=o.current,Je=m.current;!ct||!Je||(Be==="X"?Je.normal.set(1,0,0):Be==="Y"?Je.normal.set(0,1,0):Je.normal.set(0,0,1),Je.constant=-Ee,Ge&&(Je.normal.multiplyScalar(-1),Je.constant=-Je.constant),ct.localClippingEnabled=le,ct.clippingPlanes=le?[Je]:[])},de=le=>{const Ee=v.current;Ee&&(L(Ee[le]),it(0))},xe=le=>{le.traverse(Ee=>{Ee.geometry?.dispose&&Ee.geometry.dispose(),Ee.material&&(Array.isArray(Ee.material)?Ee.material:[Ee.material]).forEach(Ge=>Ge?.dispose?.())})},Ne=()=>{const le=p.current;if(le)for(;le.children.length>0;){const Ee=le.children[0];le.remove(Ee),xe(Ee)}c.current=[],ee(null),ne(null)},De=()=>{const le=s.current,Ee=l.current;Ee&&(le?.remove(Ee),xe(Ee)),l.current=null,d.current=[],_.current=null,v.current=null,L(null),it(0),Ke(!1),Ne()},Me=le=>{const Ee=p.current;if(!Ee)return;const Be=_.current?.radius??1,Ge=Math.max(Be*.01,.2)*.6,ct=new ko(Ge,16,16),Je=new Bo({color:16739072,transparent:!0,opacity:.6}),qe=new Ft(ct,Je);qe.position.copy(le),Ee.add(qe)},We=(le,Ee)=>{const Be=p.current;if(!Be)return;const Ge=new yt().setFromPoints([le,Ee]),ct=new sr({color:16739072}),Je=new Sl(Ge,ct);Be.add(Je)},U=()=>{const le=l.current,Ee=a.current,Be=u.current,Ge=s.current;if(!le||!Ee||!Be||!Ge)return;const ct=new Bi().setFromObject(le);if(ct.isEmpty())return;const Je=ct.getSize(new B),qe=ct.getCenter(new B);le.position.sub(qe);const Et=Math.max(Je.x,Je.y,Je.z),Tt=Math.max(Et*.5,.001),Rt=Ee.fov*Math.PI/180;let x=Tt/Math.tan(Rt/2);x=Math.max(x*1.3,.5),Ee.near=Math.max(.01,x/200),Ee.far=x*200,Ee.updateProjectionMatrix(),Ee.position.set(x,x,x),Be.minDistance=Math.max(.01,Tt*.2),Be.maxDistance=Tt*25,Be.target.set(0,0,0),Be.update(),Be.saveState(),_.current={distance:x,radius:Tt};const N=Math.max(Et*1.5,10);h.current&&Ge.remove(h.current);const k=new _u(N,20,8947848,14540253);k.visible=se.current,h.current=k,Ge.add(k),f.current&&Ge.remove(f.current);const V=new vu(Math.max(Et*.6,5));V.visible=$.current,f.current=V,Ge.add(V);const F=Math.max(Je.x*.5,.01),oe=Math.max(Je.y*.5,.01),_e=Math.max(Je.z*.5,.01),Re={X:{min:-F,max:F,step:Math.max(F/60,.01)},Y:{min:-oe,max:oe,step:Math.max(oe/60,.01)},Z:{min:-_e,max:_e,step:Math.max(_e/60,.01)}};v.current=Re,L(Re[Te]),it(0)},fe=()=>{const le=u.current;le&&(le.reset(),le.update())},ge=le=>{const Ee=a.current,Be=u.current,Ge=_.current;if(!Ee||!Be)return;const ct=Ge?.distance??10,Je=le.clone().normalize().multiplyScalar(ct);Ee.position.set(Je.x,Je.y,Je.z),Be.target.set(0,0,0),Be.update()},be=le=>{const Ee=a.current,Be=u.current;if(!Ee||!Be)return;const Ge=new B().copy(Ee.position).sub(Be.target).multiplyScalar(le);Ee.position.copy(Be.target).add(Ge),Ee.updateProjectionMatrix(),Be.update()},ce=()=>{const le=r.current;le&&(document.fullscreenElement?document.exitFullscreen?.():le.requestFullscreen?.())},ie=le=>{le.getAttribute("normal")||le.computeVertexNormals();const Ee=!!le.getAttribute("color"),Be=new El({color:Ee?16777215:10134450,metalness:.1,roughness:.6,vertexColors:Ee});return new Ft(le,Be)},Le=le=>t==="3mf"?new Om().parse(le):ie(t==="ply"?new Bm().parse(le):new Hm().parse(le)),Ve=le=>{const Ee=s.current;if(!Ee){xe(le);return}De(),l.current=le,Ee.add(le);const Be=20;le.traverse(Ge=>{if(Ge.isMesh&&Ge.geometry){const ct=new ru(Ge.geometry,Be),Je=new sr({color:0,transparent:!0,opacity:.7}),qe=new Ho(ct,Je);qe.visible=O.current,Ge.add(qe),d.current.push(qe)}}),pe(O.current),we(te.current),U(),R(null),Ke(!0),me("ready")};Ie.useEffect(()=>{const le=n.current;if(!le)return;le.innerHTML="";const Ee=new eu;Ee.background=new je(16777215),s.current=Ee;const Be=new zn;p.current=Be,Ee.add(Be),c.current=[],ee(null),ne(null);const Ge=new im({antialias:!0});Ge.setPixelRatio(window.devicePixelRatio);const ct=Math.max(le.clientHeight,M.current);Ge.setSize(le.clientWidth,ct),Ge.setClearColor(16777215,1),"outputColorSpace"in Ge&&(Ge.outputColorSpace=Dt),o.current=Ge,le.appendChild(Ge.domElement);const Je=new sn(45,le.clientWidth/ct,.1,1e4);Je.position.set(2,2,2),a.current=Je;const qe=new sm(Je,Ge.domElement);qe.enableDamping=!0,qe.dampingFactor=.08,qe.screenSpacePanning=!0,qe.autoRotate=re,u.current=qe;const Et=new du(16777215,6710886,.9);Ee.add(Et);const Tt=new ya(16777215,.9);Tt.position.set(6,10,8),Ee.add(Tt);const Rt=new ya(16777215,.4);Rt.position.set(-6,-4,-6),Ee.add(Rt);const x=new bn(new B(0,0,1),0);m.current=x,Ue(he,nt,Te,D);const N=()=>{if(!n.current||!o.current||!a.current)return;const F=n.current.clientWidth,oe=Math.max(n.current.clientHeight,M.current);o.current.setSize(F,oe),a.current.aspect=F/oe,a.current.updateProjectionMatrix()};A.current=N,window.addEventListener("resize",N);let k=0;const V=()=>{qe.update(),Ge.render(Ee,Je),k=requestAnimationFrame(V)};return V(),()=>{cancelAnimationFrame(k),window.removeEventListener("resize",N),qe.dispose(),De(),h.current&&(Ee.remove(h.current),h.current.geometry?.dispose?.(),h.current?.material?.dispose?.(),h.current=null),f.current&&(Ee.remove(f.current),f.current.geometry?.dispose?.(),f.current?.material?.dispose?.(),f.current=null),p.current&&(Ee.remove(p.current),p.current=null),Ge.dispose(),le.contains(Ge.domElement)&&le.removeChild(Ge.domElement),o.current=null,a.current=null,u.current=null,s.current=null,m.current=null,A.current=null}},[]),Ie.useEffect(()=>{if(!s.current)return;let le=!0;const Ee=new AbortController,{signal:Be}=Ee,Ge=async()=>{try{const qe=await fetch(i,{method:"HEAD",signal:Be});if(!qe.ok)return null;const Et=el(qe.headers.get("content-length"));return Et!==null&&S.current.set(ve,Et),Et}catch(qe){if(qe?.name==="AbortError")throw qe;return null}},ct=async(qe,Et)=>{let Tt=Et;const Rt=el(qe.headers.get("content-length"));if(Rt!==null&&(Tt=Rt,S.current.set(ve,Rt),Pe(Rt),Rt>Qa&&T!==ve))return me("confirm"),Ee.abort(),null;if(!qe.body){const oe=await qe.arrayBuffer();return Ce(oe.byteLength),Tt===null&&Pe(oe.byteLength),oe}const x=qe.body.getReader(),N=[];let k=0;for(;;){const{done:oe,value:_e}=await x.read();if(oe)break;_e&&(N.push(_e),k+=_e.byteLength,Ce(k))}Tt===null&&Pe(k);const V=new Uint8Array(k);let F=0;return N.forEach(oe=>{V.set(oe,F),F+=oe.byteLength}),V.buffer};return(async()=>{De(),R(null),Ce(0),Pe(null),me("checking");try{let qe=S.current.get(ve)??null;if(qe===null&&(qe=await Ge(),!le||Be.aborted))return;if(qe!==null&&Pe(qe),qe!==null&&qe>Qa&&T!==ve){me("confirm");return}me("downloading");const Et=await fetch(i,{signal:Be});if(!Et.ok)throw new Error(`HTTP ${Et.status}`);const Tt=await ct(Et,qe);if(!Tt||!le||Be.aborted)return;me("parsing");const Rt=Le(Tt);if(!le||Be.aborted){xe(Rt);return}Ve(Rt)}catch(qe){if(!le||qe?.name==="AbortError")return;De(),me("ready"),R(`Failed to load 3D model: ${qe instanceof Error?qe.message:"unknown error"}`)}})(),()=>{le=!1,Ee.abort()}},[T,t,ve,i]),Ie.useEffect(()=>{u.current&&(u.current.autoRotate=re)},[re]),Ie.useEffect(()=>{const le=()=>{W(document.fullscreenElement===r.current)};return document.addEventListener("fullscreenchange",le),()=>document.removeEventListener("fullscreenchange",le)},[]),Ie.useEffect(()=>{if(!A.current)return;const le=requestAnimationFrame(()=>A.current?.());return()=>cancelAnimationFrame(le)},[ae]),Ie.useEffect(()=>{h.current&&(h.current.visible=w)},[w]),Ie.useEffect(()=>{f.current&&(f.current.visible=j)},[j]),Ie.useEffect(()=>{pe(P)},[P]),Ie.useEffect(()=>{we(y)},[y]),Ie.useEffect(()=>{Ue(he,nt,Te,D)},[he,nt,Te,D]),Ie.useEffect(()=>{de(Te)},[Te]),Ie.useEffect(()=>{if(!H){Ne();return}Ne();const le=o.current,Ee=a.current;if(!le||!Ee)return;const Be=le.domElement,Ge=ct=>{if(!o.current||!a.current||!l.current)return;const Je=Be.getBoundingClientRect();if(!Je.width||!Je.height)return;const qe=(ct.clientX-Je.left)/Je.width*2-1,Et=-((ct.clientY-Je.top)/Je.height)*2+1,Tt=new gu;Tt.setFromCamera({x:qe,y:Et},a.current);const Rt=Tt.intersectObject(l.current,!0);if(!Rt.length)return;const x=Rt[0].point.clone();if(c.current.length>=2&&Ne(),c.current.push(x),Me(x),c.current.length===2){const[N,k]=c.current,V=new B().subVectors(k,N);We(N,k),ee(V.length()),ne({x:Math.abs(V.x),y:Math.abs(V.y),z:Math.abs(V.z)})}};return Be.addEventListener("click",Ge),()=>{Be.removeEventListener("click",Ge)}},[H,i,t]);const tt={fontSize:12,padding:"2px 6px",borderRadius:4,border:"1px solid #c8c8c8",background:"#f7f7f7",cursor:"pointer"},Xe=le=>({...tt,background:le?"#1f6feb":tt.background,borderColor:le?"#1f6feb":"#c8c8c8",color:le?"#ffffff":"#333333"}),$t={...tt,background:"#1f6feb",borderColor:"#1f6feb",color:"#ffffff"},Jt={position:"relative",width:ae?"100vw":"100%",height:ae?"100vh":e,background:"#ffffff",overflow:"hidden"},Hi=q==="downloading",Qt=$e!==null&&$e>0,ai=Qt?Math.min(100,Math.round(ue/$e*100)):null,li=tl($e),ki=tl(ue),ci=!C&&q!=="ready";return Ze.jsx("div",{children:C?Ze.jsx("div",{className:"alert alert-danger",role:"alert",children:C}):Ze.jsxs("div",{ref:r,style:Jt,children:[Ze.jsx("div",{ref:n,style:{width:"100%",height:"100%"}}),ci?Ze.jsx("div",{style:{position:"absolute",inset:0,display:"flex",alignItems:"center",justifyContent:"center",padding:16,background:"rgba(255,255,255,0.72)",zIndex:3},children:Ze.jsxs("div",{role:"status",style:{width:"min(420px, 100%)",padding:18,borderRadius:10,border:"1px solid #dbe4ef",background:"rgba(255,255,255,0.96)",boxShadow:"0 8px 30px rgba(15, 23, 42, 0.12)"},children:[Ze.jsx("div",{style:{fontSize:14,fontWeight:600,color:"#1f2937",marginBottom:8},children:q==="confirm"?"Large 3D preview":q==="skipped"?"Preview not downloaded":q==="parsing"?"Preparing 3D preview":q==="downloading"?"Downloading 3D preview":"Checking preview size"}),Ze.jsx("div",{style:{fontSize:13,lineHeight:1.5,color:"#475569",marginBottom:q==="confirm"||q==="skipped"?16:12},children:q==="confirm"?li?`This 3D preview is ${li}. Download it now?`:"This 3D preview is larger than 5 MB. Download it now?":q==="skipped"?"The 3D preview download was canceled before starting.":q==="parsing"?"The file is downloaded. Building the 3D preview now.":q==="downloading"?Qt&&ai!==null?`Downloaded ${ki} of ${li} (${ai}%).`:`Downloaded ${ki}.`:"Checking the file size before starting the download."}),q==="checking"||q==="downloading"||q==="parsing"?Ze.jsx("progress",{style:{width:"100%",height:12},value:Hi&&Qt?ue:void 0,max:Hi&&Qt?$e:void 0}):null,q==="confirm"?Ze.jsxs("div",{style:{display:"flex",justifyContent:"flex-end",gap:8},children:[Ze.jsx("button",{style:tt,type:"button",onClick:()=>me("skipped"),children:"Cancel"}),Ze.jsx("button",{style:$t,type:"button",onClick:()=>g(ve),children:"Download"})]}):null,q==="skipped"?Ze.jsx("div",{style:{display:"flex",justifyContent:"flex-end"},children:Ze.jsx("button",{style:$t,type:"button",onClick:()=>g(ve),children:"Download preview"})}):null]})}):null,Ze.jsxs("div",{style:{position:"absolute",left:8,right:8,bottom:8,display:"flex",flexWrap:"wrap",gap:8,padding:8,borderRadius:6,border:"1px solid #e2e2e2",background:"rgba(255,255,255,0.9)",alignItems:"center",zIndex:2,opacity:K?1:.6,pointerEvents:K?"auto":"none"},children:[Ze.jsx("button",{style:tt,type:"button",onClick:U,children:"Fit"}),Ze.jsx("button",{style:tt,type:"button",onClick:fe,children:"Reset"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>ge(new B(0,0,1)),children:"Front"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>ge(new B(1,0,0)),children:"Right"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>ge(new B(0,1,0)),children:"Top"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>ge(new B(1,1,1)),children:"Iso"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>be(.8),children:"Zoom +"}),Ze.jsx("button",{style:tt,type:"button",onClick:()=>be(1.25),children:"Zoom -"}),Ze.jsx("button",{style:Xe(w),type:"button",onClick:()=>Q(le=>!le),children:"Grid"}),Ze.jsx("button",{style:Xe(j),type:"button",onClick:()=>Z(le=>!le),children:"Axes"}),Ze.jsx("button",{style:Xe(P),type:"button",onClick:()=>I(le=>!le),children:"Edges"}),Ze.jsx("button",{style:Xe(y),type:"button",onClick:()=>E(le=>!le),children:"Wireframe"}),Ze.jsx("button",{style:Xe(he),type:"button",onClick:()=>ye(le=>!le),children:"Section"}),he&&J?Ze.jsxs(Ze.Fragment,{children:[Ze.jsx("span",{style:{fontSize:12,color:"#444"},children:"Axis"}),Ze.jsx("button",{style:Xe(Te==="X"),type:"button",onClick:()=>ze("X"),children:"X"}),Ze.jsx("button",{style:Xe(Te==="Y"),type:"button",onClick:()=>ze("Y"),children:"Y"}),Ze.jsx("button",{style:Xe(Te==="Z"),type:"button",onClick:()=>ze("Z"),children:"Z"}),Ze.jsx("button",{style:Xe(D),type:"button",onClick:()=>z(le=>!le),children:"Flip"}),Ze.jsx("span",{style:{fontSize:12,color:"#444"},children:"Offset"}),Ze.jsx("input",{type:"range",min:J.min,max:J.max,step:J.step,value:nt,onChange:le=>it(Number(le.target.value)),style:{width:200}})]}):null,Ze.jsx("button",{style:Xe(re),type:"button",onClick:()=>X(le=>!le),children:"Auto-rotate"}),Ze.jsx("button",{style:Xe(ae),type:"button",onClick:ce,children:"Full screen"}),Ze.jsx("button",{style:Xe(H),type:"button",onClick:()=>G(le=>!le),children:"Measure"}),H?Ze.jsx("span",{style:{fontSize:12,color:"#333"},children:Y===null||!b?"Measure: click two points":`Measure: ${Y.toFixed(2)} (dX ${b.x.toFixed(2)}, dY ${b.y.toFixed(2)}, dZ ${b.z.toFixed(2)})`}):null,Ze.jsx("span",{style:{fontSize:11,color:"#666"},children:"Drag to rotate, right drag to pan, wheel to zoom"})]})]})})};export{Vm as default};
